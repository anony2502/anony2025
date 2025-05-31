"""
    1. naivellm
"""
import argparse, time, os, traceback, json, subprocess
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import Client
from langchain_core.chat_history import (
    BaseChatMessageHistory,
    InMemoryChatMessageHistory,
)
from langchain_core.runnables.history import RunnableWithMessageHistory
from utils.configs import LANGCHAIN_API_KEY, REPO_BASE, DATA_BASE, OUTPUT_BASE, src_files
from utils.llm import model_gpt41 as model
from utils.gitter import UpdateRepo
from utils.parser import get_code_without_comments
from utils.logger import logger
from pipeline_helper import *
from prompt import *
from utils.formatter import formatted_java_code
# # Langsmith setup
# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_PROJECT"] = f"naivellm"
# os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
# os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
# client = Client()

prompt_generate = ChatPromptTemplate.from_messages([
    ("system", system_prompt_2),
    ("user", prompt_2)
])

chain_2 = prompt_generate | model | StrOutputParser()

def gen_test(prod_diff, test_src, context) -> str:
    query = {
        "FOCAL_DIFF": prod_diff,
        "TEST_SRC": test_src,
        "CONTEXT": context
    }
    res = chain_2.invoke(query)
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
    # Set repo_name, repo_path, output_file
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
    
    build_pass = []
    test_pass = []
    import_error = []

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
            # generate updated test method
            test_gen = gen_test(focal_diff, test_src_aligned, '')
            test_gen_code = extract_code(test_gen)
            code_gen, imports_gen = split_imports_and_test_code(test_gen_code)
            logger.info(test_gen_code)
            if not test_gen: 
                value['test_gen'] = '// Fail to generate updated test method.\n'
                continue
            value['test_gen'] = code_gen
            value["imports_gen"] = imports_gen
            compile_result, _, test_info = build_test(value)

            if compile_result == 0:
                test_pass.append(key)
                build_pass.append(key)
                value['test_pass'] = True
                value['build_pass'] = True
            elif len(test_info) > 0:
                build_pass.append(key)
                value['build_pass'] = True

        except Exception as e:
            traceback.print_exc()
            value['test_gen'] = '// Fail to generate updated test method.\n'
            value['exception_while_gen_tests'] = repr(e)

        outputs.append(value)
        write_json(output_file, outputs)
        logger.info(f"{'=============================='*5}")
        time.sleep(5)

    logger.info(f"===============TEST PASS : {len(test_pass)}=====================")
    logger.info(f"=={test_pass}==")
    logger.info(f"===============BUILD PASS : {len(build_pass)}=====================")
    logger.info(f"=={build_pass}==")
    logger.info(f"===============IMPORT ERROR : {len(import_error)}=====================")
    logger.info(f"=={import_error}==")

if __name__  == "__main__":
    logger.set_log_file("logs/naivellm.log")

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=int, required=True, help='Input dataset file index.')
    parser.add_argument("-i", "--input", type=str, help='Input dataset filename (under DATA_BASE).')
    parser.add_argument("-o", "--output", type=str, default='naivellm', help='Output directory (under OUTPUT_BASE).')
    args = parser.parse_args()
    idx = args.file
    output_file = args.output

    input_file = src_files[idx]
    main(input_file, output_file)