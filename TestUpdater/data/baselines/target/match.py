import json

# file_a = 'apache/rocketmq/dataset_bak.json'
file_a = 'prebid/prebid-server-java/codeMining/changed_tests.json'
# file_a = 'OpenAPITools/openapi-generator/codeMining/changed_tests.json'
file_b = '/data/yuanhezhang/test-updater/TestUpdate/data/verified_prebid_prebid-server-java.json'
# file_b = '/data/yuanhezhang/test-updater/TestUpdate/data/verified_OpenAPITools_openapi-generator.json'

# 读取两个 JSON 文件
with open(file_a, "r") as f:
    data_a = json.load(f)

with open(file_b, "r") as f:
    data_b = json.load(f)

# 转换 B 文件为集合方便匹配 (aCommit, bCommit, bPath)
b_commit_triplets = set(
    (item["commit_src"][:9], 
     item["commit_tgt"][:9], 
     item["changed_test"].split('#')[0],
     item["changed_test"].split('#')[1]) for item in data_b
)
print(b_commit_triplets)

# 筛选出同时匹配 commit 和路径的项
matched = []
for item in data_a:
    triplet = (item["bCommit"], item["aCommit"], item["bPath"], item["name"].split('.')[-1].replace('()', ''))
    print(triplet)
    if triplet in b_commit_triplets:
        matched.append(item)

# 输出匹配结果
print(f"找到 {len(matched)} 个匹配项")
with open("matched.json", "w") as f:
    json.dump(matched, f, indent=2)
