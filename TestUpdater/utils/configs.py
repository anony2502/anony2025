# The FULL PATH of all the repos, cannot be ./repos
REPO_BASE = ""
# The FULL PATH of the project
FILE_BASE = ""
# LLM API keys
OPENAI_API_KEY = "sk-xxxxxxxx"
DEEPSEEK_API_KEY = "sk-xxxxxxxx"
# LangChain LangSmith to trace LLM queries
LANGCHAIN_API_KEY = ""

# The path of dataset jsons
DATA_BASE = FILE_BASE + "/data"
# The path to output results
OUTPUT_BASE = FILE_BASE + "/output"

TIME_ZONE = "UTC"

mvn_dict = {
    "mvnw": "mvnw",
    "3.8.6": "",
    "3.8.1": "",
    "3.6.3": "",
    "3.9.9": ""
}
java_dict = {
    "1.7": "",
    "7": "",
    "1.8.0": "",
    "1.8": "",
    "8": "",
    "11": "",
    "17": "",
    "21": "",
    "22": ""
}

src_files = [
    "test_part.json",
    "verified_Aiven-Open_klaw.json",
    "verified_alibaba_nacos.json",
    "verified_apache_rocketmq.json",
    "verified_apache_shenyu.json",
    "verified_OpenAPITools_openapi-generator.json",
    "verified_prebid_prebid-server-java.json",
    "verified_shred_acme4j.json",  
]