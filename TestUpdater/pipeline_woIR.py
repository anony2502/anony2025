import argparse, time, os, traceback, json, subprocess
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import Client

from utils.multilspy import SyncLanguageServer
from utils.multilspy.multilspy_config import MultilspyConfig
from utils.multilspy.multilspy_logger import MultilspyLogger
from utils.configs import LANGCHAIN_API_KEY, REPO_BASE, DATA_BASE, OUTPUT_BASE, src_files
from utils.llm import model_deepseek, model_gpt4omini, model_llama, model_gpt41
from utils.gitter import UpdateRepo
from utils.parser import get_code_without_comments
from utils.logger import logger
from pipeline_helper import *
from prompt import *
from utils.formatter import formatted_java_code

# Java Language Server
lsp_config = MultilspyConfig.from_dict(
    {"code_language": "java", "trace_lsp_communication": True}
)
lsp_logger = MultilspyLogger()

model = None
output_dir = "pipeline_woIR"
# Langsmith setup
# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_PROJECT"] = f"pipeline"
# os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
# os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
# client = Client()

def gen_info(focal_diff, test_src) -> str:
    query = {
        "FOCAL_DIFF": focal_diff,
        "TEST_SRC": test_src
    }
    prompt_analyse = ChatPromptTemplate.from_messages([
        ("system", system_prompt_1),
        ("user", prompt_1_0)
    ])
    chain = prompt_analyse | model | StrOutputParser()

    res = chain.invoke(query)
    return res

def gen_filter(focal_diff: str, test_src: str, context: str, answer: str) -> str:
    query = {
        "FOCAL_DIFF": focal_diff,
        "TEST_SRC": test_src,
        "CONTEXT": context
    }
    prompt_filter = ChatPromptTemplate.from_messages([
        ("system", system_prompt_1),
        ("user", prompt_1_0),
        AIMessage(content=answer),
        ("user", prompt_1_1)
    ])
    chain = prompt_filter | model | StrOutputParser()
    res = chain.invoke(query)
    return res


def gen_test(prod_diff, test_src, context) -> str:
    query = {
        "FOCAL_DIFF": prod_diff,
        "TEST_SRC": test_src,
        "CONTEXT": context
    }
    prompt_generate = ChatPromptTemplate.from_messages([
        ("system", system_prompt_2),
        ("user", prompt_2)
    ])
    chain = prompt_generate | model | StrOutputParser()
    res = chain.invoke(query)
    return res

def verify_code(prod_diff, test_src, context: str, error_info: str, answer_2: str) -> str:
    prompt_verify = ChatPromptTemplate.from_messages([
        ("system", system_prompt_2),
        ("user", prompt_2),
        AIMessage(content=answer_2),
        ("user", prompt_3)
    ])
    chain_3 = prompt_verify | model | StrOutputParser()
    query = {
        "FOCAL_DIFF": prod_diff,
        "TEST_SRC": test_src,
        "CONTEXT": context,
        "ERRORINFO": error_info
    }
    res = chain_3.invoke(query)
    return res

def basic_answer(prod_diff, test_src, context: str, answer_2: str) -> str:
    prompt_verify = ChatPromptTemplate.from_messages([
        ("system", system_prompt_2),
        ("user", prompt_2),
        AIMessage(content=answer_2),
        ("user", basic_ans_prompt)
    ])
    chain_4 = prompt_verify | model | StrOutputParser()
    query = {
        "FOCAL_DIFF": prod_diff,
        "TEST_SRC": test_src,
        "CONTEXT": context
    }
    res = chain_4.invoke(query)
    return res

def collect_definition(info, repo_path, proj, repo, lsp: SyncLanguageServer):
    res = []
    
    for func in info["method"]:
        func_info = get_function(func, repo_path, proj, repo, lsp)
        res.append(func_info)
    
    if len(info["class"]) > 5:
        info["class"] = info["class"][:5]
    for clas in info["class"]:
        clas_info = get_class(clas, repo_path, proj, repo, lsp)
        res.append(clas_info)

    res = '\n'.join(res)
    return res

def get_diff_method(src: str, tgt: str) -> str:
    src_clean = get_code_without_comments(src)
    src_fmt = formatted_java_code(src_clean)
    tgt_clean = get_code_without_comments(tgt)
    tgt_fmt = formatted_java_code(tgt_clean)
    format_prefix = "@@\n\n"
    if src_fmt and tgt_fmt:
        diff_str = get_diff(src_fmt, tgt_fmt)
    else:
        diff_str = get_diff(src, tgt)
    res = diff_str[diff_str.find(format_prefix) + len(format_prefix) :]
    return res


def split_imports_and_test_code(java_code):
    lines = java_code.strip().split("\n")
    import_lines = []
    test_lines = []
    for idx, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("import\t"):
            import_lines.append(line)
        if line.find("@Test") != -1:
            test_lines = lines[idx:]
            break
    return "\n".join(test_lines), "\n".join(import_lines)

def main(input_file: str, output_file: str, process_continue=True):
    # Set repo_name, repo_path, output_dir
    sample_dict = read_json(os.path.join(DATA_BASE, input_file))
    repo_name = sample_dict[0]['repo_name']
    repo_path = os.path.join(REPO_BASE, repo_name)
    output_dir = os.path.join(OUTPUT_BASE, output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_file = os.path.join(output_dir, input_file)

    outputs = []
    process_count = 0
    # continue to process
    if os.path.exists(output_file) and process_continue:
        with open(output_file, "r") as f:
            content = json.load(f)
        if content:
            outputs = content
            process_count = len(outputs)
            logger.info(f"Continue processing from item: {len(outputs)}")
    if process_count == len(sample_dict):
        return
    
    build_pass = []
    test_pass = []
    import_error = []

    # initialize
    lsp = SyncLanguageServer.create(lsp_config, lsp_logger, repo_path)
    logger.info(f"Initializing Language Server for {repo_name}...")
    with lsp.start_server():
        for key, value in enumerate(sample_dict[process_count:]):
            logger.info(f"==========> Processing item: {key} <==========")
            focal_src = value['prod_code_src']
            focal_tgt = value['prod_code_tgt']
            test_src = value['test_code_src']
            test_src_aligned = align_code(test_src)

            update_repo = UpdateRepo(repo_path, value["commit_tgt"])
            update_repo.checkout_tgt()
            focal_diff = get_diff_method(focal_src, focal_tgt)

            try:
                # ask LLM for info needed, return with method/class names in JSON
                info_gen_ori = gen_info(focal_diff, test_src_aligned)
                info_gen = extract_json(info_gen_ori)
                info_gen = json.loads(info_gen)
                logger.info(f"--- info for item {key}:{info_gen}")

                # cllect definitions for method/class
                context = collect_definition(info_gen, repo_path, value, update_repo, lsp)
                # collect references
                reference = ""
                variables = get_varibles(value, update_repo)
                if variables:
                    reference = "Varibles defined in test class that you can derectly use:\n"
                    reference += f"```java\n{variables}\n```\n"
                
                # filter information
                filtered_info = gen_filter(focal_diff, test_src_aligned, context, info_gen_ori)
                
                context = filtered_info + "\n" + reference
                logger.info(context)

                # generate updated test method
                test_gen = gen_test(focal_diff, test_src_aligned, context)
                test_gen_code = extract_code(test_gen)
                code_gen, imports_gen = split_imports_and_test_code(test_gen_code)
                logger.info(test_gen_code)
                if not test_gen: 
                    value['test_gen'] = '// Fail to generate updated test method.\n'
                    continue
                value['test_gen'] = code_gen
                value["imports_gen"] = imports_gen
                compile_result, error_info, test_info = build_test(value)
                
                # get result
                if compile_result == 0:
                    test_pass.append(key)
                    value['test_pass'] = True
                    build_pass.append(key)
                    value['build_pass'] = True
                elif len(test_info) > 0:
                    build_pass.append(key)
                    value['build_pass'] = True
                cannot_find_symbol = [line for line in error_info if 'cannot find symbol' in line]
                if len(cannot_find_symbol) > 0:
                    import_error.append(key)

            except Exception as e:
                traceback.print_exc()
                value['test_gen'] = '// Fail to generate updated test method.\n'
                value['exception_while_gen_tests'] = repr(e)

            outputs.append(value)
            write_json(output_file, outputs)
            logger.info(f"{'=============================='*5}")
            time.sleep(5)

    # close language server
    subprocess.run(["pkill", "-f", "language_servers"])
    logger.info(f"===============TEST PASS : {len(test_pass)}=====================\n{test_pass}==")
    logger.info(f"===============BUILD PASS : {len(build_pass)}=====================\n{build_pass}==")
    logger.info(f"===============IMPORT ERROR : {len(import_error)}=====================\n=={import_error}==")

if __name__  == "__main__":
    logger.set_log_file("logs/pipeline_woIR.log")

    model_map = {
        "deepseek": model_deepseek,
        "gpt4omini": model_gpt4omini,
        "llama": model_llama,
        "gpt41": model_gpt41
    }

    # Parameters for LLM to use
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", type=str, required=True, help='LLM name.')
    args = parser.parse_args()

    model_name = args.model
    output_dir = output_dir + model_name
    model = model_map[model_name]

    # start processing 7 project
    for idx in range(1, 8):
        input_file = src_files[idx]
        main(input_file, output_dir)