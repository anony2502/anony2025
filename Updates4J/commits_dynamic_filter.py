import os, sys, json, traceback, multiprocessing, logging
import subprocess as sp
import xml.etree.ElementTree as ET
from tqdm import tqdm
from func_timeout import func_set_timeout
from func_timeout.exceptions import FunctionTimedOut
from configs import *

logging.basicConfig(filename='df.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

#TODO config path
unverified_commits_path = "unverified_commits/"
repo_store_path = ""

verified_commits_path = "verified_commits/"
exp_path = "exceptions_occurred"
num_cores = 5
timeout = 1200

mvn_repos = {	
    "shred/acme4j": "3.8.1",
    "alibaba/nacos": "3.8.6",
    "apache/hertzbeat":	"3.8.6",
    "apache/rocketmq": "3.6.3",
    "OpenAPITools/openapi-generator": "3.9.9",
    "javaparser/javaparser": "3.9.9",
    "apache/shenyu": "3.6.3",
    "apache/dolphinscheduler": "3.8.6", #verify
    "apache/dubbo": "3.9.9"
}
default_mvn_version = "3.8.6"

def checkout(repo_path, commit):
    p = sp.run(['git', 'reset', '--hard', 'HEAD'],
           cwd=repo_path, stdout=sp.PIPE, stderr=sp.PIPE)
    
    # p = sp.run(['git', 'clean', '-df'],
    #        cwd=repo_path, stdout=sp.PIPE, stderr=sp.PIPE)

    p = sp.run(['git', 'checkout', commit], cwd=repo_path,
           stdout=sp.PIPE, stderr=sp.PIPE)
    return p.stdout.decode(), p.stderr.decode()

def parse_java_version(repo_path):
    pom_file = os.path.join(repo_path, "pom.xml")
    tree = ET.parse(pom_file)
    root = tree.getroot()
    namespaces = {'ns': 'http://maven.apache.org/POM/4.0.0'}

    properties = root.find('./ns:properties', namespaces)
    if properties is not None:
        for p in java_find_properties:
            version = properties.find(f'./ns:{p}', namespaces)
            if version is not None:
                v = version.text.strip()
                if v in jdk_versions:
                    return v
                v = v.split('-')[0]
                if v in jdk_versions:
                    return v
                v = v.split('.')[0]
                if v in jdk_versions:
                    return v
    # Additional search
    vs = []
    vs.append(root.find('.//ns:plugin[ns:artifactId="maven-compiler-plugin"]/ns:configuration/ns:source', namespaces))
    vs.append(root.find('.//ns:plugin[ns:artifactId="maven-compiler-plugin"]/ns:configuration/ns:target', namespaces))
    vs.append(root.find('.//ns:plugin[ns:artifactId="maven-compiler-plugin"]/ns:configuration/ns:release', namespaces))
    vs.append(root.find('.//ns:plugin[ns:artifactId="maven-compiler-plugin"]/ns:executions/ns:execution/ns:configuration/ns:source', namespaces))
    vs.append(root.find('.//ns:plugin[ns:artifactId="maven-compiler-plugin"]/ns:executions/ns:execution/ns:configuration/ns:target', namespaces))
    vs.append(root.find('.//ns:plugin[ns:artifactId="maven-compiler-plugin"]/ns:executions/ns:execution/ns:configuration/ns:release', namespaces))

    for v in vs:
        if v is None:
            continue
        version = v.text.strip()
        if version in jdk_versions:
            return version
    return None

@func_set_timeout(timeout)
def run_test_with_time_limit(mvnw, env, test_case, repo_path, module, command=None):
    path_env = env["PATH"]
    path_env = f"{env['JAVA_HOME']}/bin:{env['MAVEN_HOME']}/bin:{path_env}"
    env["PATH"] = path_env
    default = [
        "mvn",
        "-T1C",
        "clean",
        "test",
        f'-Dtest={test_case}',  
        "-Dsurefire.failIfNoSpecifiedTests=false", 
        "-DfailIfNoTests=false", 
        "-Dmaven.test.skip=false", 
        "-DskipTests=false",
    ]
    if mvnw:
        default[0] = './mvnw'

    if module:
        default = default[:2] + ["-pl",f"{module}", "--also-make"] + default[2:]
    
    default.extend(MVN_SKIPS)
    logging.info(' '.join(default))
    logging.info(env["PATH"])
    run = sp.run(default, env=env, stdout=sp.PIPE, stderr=sp.PIPE, cwd=repo_path)
    stdout = run.stdout.decode()
    stderr = run.stderr.decode()
    logging.info(stderr)
    return stdout, stderr

def run_test(mvnw, env, test_case, repo_path, module, command=None):
    try:
        return run_test_with_time_limit(mvnw, env, test_case, repo_path, module, command)
    except (Exception, FunctionTimedOut) as e:
        exp = traceback.format_exc()
        if not os.path.exists(exp_path):
            os.makedirs(exp_path)
        c = len(os.listdir(exp_path))
        with open(os.path.join(exp_path, f"exp_{c}.json"), 'w') as f:
            json.dump(exp, f, indent=2)
        return "", ""

def check_test(commit, test_case, repo_path, java_version, full_name, module):
    logging.info(f"java_version{java_version}")
    output, error = checkout(repo_path, commit)
    command = None
    if mvn_repos.get(full_name):
        mvn_path = mvn_dict[mvn_repos[full_name]]
    else:
        mvn_path = mvn_dict[default_mvn_version]
    mvn_version = mvn_path.split('/')[-1].split('-')[-1]
    logging.info(f"mvn_version{mvn_version}")
    if java_version is not None:
        JAVA_HOME = jdk_path[java_version]
        new_env = os.environ.copy()
        new_env['JAVA_HOME'] = JAVA_HOME
        new_env['MAVEN_HOME'] = mvn_path
        output, error = run_test(False, new_env, test_case, repo_path, module, command)
        if 'BUILD SUCCESS' in output:
            return True, java_version, mvn_version
        else:
            return False, java_version, mvn_version
    else:
        for j in java_list:
            JAVA_HOME = jdk_path[j]
            new_env = os.environ.copy()
            new_env['JAVA_HOME'] = JAVA_HOME
            new_env['MAVEN_HOME'] = mvn_path
            output, error = run_test(False, new_env, test_case, repo_path, module, command)
            if 'BUILD SUCCESS' in output:
                return True, j, mvn_version
            else:
                return False, j, mvn_version
            
    if not os.path.exists(os.path.join(repo_path, 'mvnw')):
        return False, None, None
    mvn_version = "mvnw"
    if java_version is not None:
        JAVA_HOME = jdk_path[java_version]
        new_env = os.environ.copy()
        new_env['JAVA_HOME'] = JAVA_HOME
        output, error = run_test(True, new_env, test_case, repo_path, module, command)
        if 'BUILD SUCCESS' in output:
            return True, java_version, mvn_version
        else:
            return False, java_version, mvn_version
    else:
        for j in java_list:
            JAVA_HOME = jdk_path[j]
            new_env = os.environ.copy()
            new_env['JAVA_HOME'] = JAVA_HOME
            output, error = run_test(True, new_env, test_case, repo_path, module, command)
            if 'BUILD SUCCESS' in output:
                return True, j, mvn_version
            else:
                return False, j, mvn_version
    return False, None, None


def dynamic_analysis(json_file):
    with open(json_file, 'r') as f:
        commits = json.load(f)
    r = []
    full_name = json_file.split('/')[-1].replace('unverified_', '').replace('.json', '').replace('_', '/')
    logging.info(f"Processing: {full_name}")
    repo_path = os.path.join(repo_store_path, full_name)
    if not os.path.exists(repo_path):
        return 0
    if os.path.exists(os.path.join(verified_commits_path, f"verified_{full_name.replace('/', '_')}.json")):
        return 0
    java_version = parse_java_version(repo_path)
    for key, value in tqdm(enumerate(commits), total=len(commits), desc=f'Processing: {full_name}'):
        commit_src = value['commit_src']
        commit_tgt = value['commit_tgt']
        changed_test = value['changed_test']

        classname, methodname = changed_test.split('#')
        classname = classname.split('src/test/java/')[-1].replace('.java', '').replace('/', '.')
        test_case = f"{classname}#{methodname}"
        logging.info(test_case)
        module = changed_test.split('src/test/java/')[0]
        if module.endswith('/'):
            module = module[:-1]
        logging.info(module)
        compile_src, src_java_v, src_mvn_v = check_test(commit_src, test_case, repo_path, java_version, full_name, module)
        compile_tgt, tgt_java_v, tgt_mvn_v = check_test(commit_tgt, test_case, repo_path, java_version, full_name, module)
        logging.info(f"compile_src={compile_src}; compile_tgt={compile_tgt}")
        if compile_src and compile_tgt:
            value["src_java_version"] = src_java_v
            value["src_maven_version"] = src_mvn_v
            value['tgt_java_version'] = tgt_java_v
            value['tgt_maven_version'] = tgt_mvn_v
            r.append(value)
    result = []
    for idx, v in enumerate(r):
        v['test_id'] = idx
        result.append(v)
    if not os.path.exists(verified_commits_path):
        os.makedirs(verified_commits_path)
    with open(os.path.join(verified_commits_path, f"verified_{full_name.replace('/', '_')}.json"), 'w') as f:
        json.dump(result, f, indent=2)
    return 0
    
if __name__ == "__main__":
    unverified_json = [os.path.join(unverified_commits_path, l) for l in os.listdir(unverified_commits_path) if l.endswith('.json')]
    with multiprocessing.Pool(processes=num_cores) as process_pool:
        for r in process_pool.imap(dynamic_analysis, unverified_json):
            pass