import json
import pandas as pd
# file_a = 'apache/rocketmq/dataset_bak.json'
file_a = '/data/yuanhezhang/target/TaRGET/repair-collection/output/prebid/prebid-server-java/codeMining/changed_test_classes.csv'
file_b = '/data/yuanhezhang/test-updater/TestUpdate/data/verified_prebid_prebid-server-java.json'

df = pd.read_csv(file_a)
# print(df)
with open(file_b, "r") as f:
    data_b = json.load(f)

# 转换 B 文件为集合方便匹配 (aCommit, bCommit, bPath)
b_commit_triplets = set(
    (item["commit_src"][:9], 
     item["commit_tgt"][:9], 
     item["changed_test"].split('#')[0]) for item in data_b
)
print(b_commit_triplets)


filtered_df = df[
    df.apply(
        lambda row: (row['b_commit'], row['a_commit'], row['b_path']) in b_commit_triplets,
        axis=1
    )
]
print(filtered_df)
filtered_df.to_csv('matched.csv', index=False)
