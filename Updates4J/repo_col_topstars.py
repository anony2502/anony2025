import time
import json
import requests, base64
from tqdm import tqdm


# GitHub Access Token (Please replace to yours)
GITHUB_TOKEN = ""

# GitHub API Header
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}


def get_top_repos(query, total=500, per_page=100):
    """
    Fetch the top GitHub repositories sorted by stars.

    Args:
        query (str): Search query for repositories.
        total (int): Total number of repositories to fetch.
        per_page (int): Number of repositories per request (max 100).

    Returns:
        list: A list of repository data (JSON format).
    """
    url = "https://api.github.com/search/repositories"
    all_repos = []
    pages = (total // per_page) + (1 if total % per_page else 0)  # Calculate the number of pages needed

    for page in range(1, pages + 1):
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page
        }
        response = requests.get(url, params=params, headers=HEADERS)

        if response.status_code == 200:
            items = response.json().get("items", [])
            all_repos.extend(items)
            if len(all_repos) >= total:  # Stop once enough data is collected
                return all_repos[:total]
        else:
            print(f"Error {response.status_code}: {response.text}")
            break  # Stop on API failure

    return all_repos

def filter_maven_jacoco_repos(repos):
    # filter by pom.xml
    result = []
    for repo in tqdm(repos):
        # make sure not the problem of requests
        pom_url = repo['contents_url'].replace("{+path}", 'pom.xml')
        try:
            response = requests.get(
                pom_url,
                headers=HEADERS,
                timeout=100
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('encoding') == 'base64' and 'content' in data:
                    pom_content = base64.b64decode(data['content']).decode('utf-8')
                    if 'jacoco' in pom_content.lower():
                        result.append(repo)    
                        
        except requests.exceptions.RequestException as e:
            pass
    return result

if __name__ == "__main__":
    # Fetch Java Projects with most stars
    java_repos = get_top_repos("language:Java", total=500)
    maven_repos = filter_maven_jacoco_repos(java_repos)
    with open("repos_topstars.txt", "w") as f:
        f.writelines([repo['full_name'] + '\n' for repo in maven_repos])