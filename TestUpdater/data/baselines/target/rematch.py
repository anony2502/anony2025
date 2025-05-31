import json

file_a = 'prebid/prebid-server-java/codeMining/changed_tests.json'
# file_a = 'apache/rocketmq/codeMining/changed_tests.json'
file_b = '/data/yuanhezhang/test-updater/TestUpdate/data/verified_prebid_prebid-server-java.json'
# file_b = '/data/yuanhezhang/test-updater/TestUpdate/data/verified_apache_rocketmq.json'

# 读取两个 JSON 文件
with open(file_a, "r") as f:
    data_a = json.load(f)

with open(file_b, "r") as f:
    data_b = json.load(f)

# 从 A 中构建匹配 triplet 集合 (bCommit, aCommit, bPath)
a_commit_triplets = set(
    (item["bCommit"], item["aCommit"], item["bPath"], item["name"].split('.')[-1].replace('()', '')) for item in data_a
)

# 从 B 中筛选出 triplet 匹配的项
matched = []
for item in data_b:
    triplet = (
        item["commit_src"][:9],
        item["commit_tgt"][:9],
        item["changed_test"].split("#")[0],
        item["changed_test"].split("#")[1]
    )
    if triplet in a_commit_triplets:
        matched.append(item)

# 输出匹配结果
print(f"找到 {len(matched)} 个匹配项")

# 将匹配结果写回 file_b
with open('rematch.json', "w") as f:
    json.dump(matched, f, indent=2)
