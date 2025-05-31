import time
import json
import requests
from tqdm import tqdm
from repo_col_topstars import filter_maven_jacoco_repos

# GitHub Access Token (Please replace to yours)
GITHUB_TOKEN = ""

# GitHub API Header
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

def search_repos_in_github(stars, language, page, args=None):
    search_url = "https://api.github.com/search/repositories"
    query_params = {
        'q': f"stars:{stars} language:{language}{'' if args is None else f' {args}'}",
        'sort': "stars",
        'per_page': 100,
        'page': page
    }
    try:
        response = requests.get(search_url, params=query_params, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()['items']
        else:
            print(f"Failed to do large scale search in GitHub: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        return None

def large_scale_search_in_github(min_stars, language, args=None):
    result = []
    max_stars = 1000
    idx = 1
    pbar = tqdm(total=None)
    while True:
        if idx > 10:
            break
        page = search_repos_in_github(f"{min_stars}..{max_stars}", language, idx, args)
        if page is None:
            time.sleep(60)
            continue
        if len(page) == 0:
            break
        result += page
        pbar.update(len(page))
        if max_stars == result[-1]['stargazers_count']:
            idx += 1
            continue
        idx = 1
        max_stars = result[-1]['stargazers_count']
        if max_stars < 50:
            break
    collected_repos = set()
    result = [repo for repo in result if not (repo['node_id'] in collected_repos or (collected_repos.add(repo['node_id'])))]
    return result

if __name__ == "__main__":
    stars = 50
    # Collect via GitHub API
    all_repos = large_scale_search_in_github(stars, "Java", "maven in:readme")
    print(len(all_repos))
    maven_repos = filter_maven_jacoco_repos(all_repos)
    with open("repos_starrange.txt", "w") as f:
        f.writelines([repo['full_name'] + '\n' for repo in maven_repos])
    