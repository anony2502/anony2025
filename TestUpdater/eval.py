import json, os, subprocess, multiprocessing
import pandas as pd
from utils.gitter import setup_repo, UpdateRepo
from utils.logger import MyLogger
from pipeline_helper import substitute_code, add_imports
from utils.configs import mvn_dict, java_dict, FILE_BASE, REPO_BASE, TIME_ZONE

INPUT_BASE = "./output/pipelinedeepseek"
csv_file_path = "coverage/pipeline.csv"

MVN_SKIPS = [
    "-DfailIfNoTests=false",
    "-Dsurefire.failIfNoSpecifiedTests=false",
    "-Djacoco.skip=false",
    "-Dcheckstyle.skip",
    "-Dspotless.check.skip",
    "-Dspotless.apply.skip",
    "-Drat.skip",
    "-Denforcer.skip",
    "-Danimal.sniffer.skip",
    "-Dmaven.javadoc.skip",
    "-Dmaven.gitcommitid.skip",
    "-Dfindbugs.skip",
    "-Dwarbucks.skip",
    "-Dmodernizer.skip",
    "-Dimpsort.skip",
    "-Dpmd.skip",
    "-Dxjc.skip",
    "-Dair.check.skip-all",
    "-Dlicense.skip",
    "-Dremoteresources.skip",
    "-Dspotbugs.skip=true",
    # '-Dmaven.test.failure.ignore=true'
]


def build_test(exp: dict, build_pass, test_pass, import_error, output_csv, logger):

    logger.info("##" * 5 + " [" + str(exp["test_id"]) + "] " + "##" * 5)

    # checkout the repository to this given commit
    repo_root = os.path.join(REPO_BASE, exp["repo_name"])
    prod_class = exp["changed_prod"].split("#")[0].split("/")[-1].split(".")[0]
    changed_test = exp["changed_test"]
    classname, methodname = changed_test.split("#")
    classname = (
        classname.split("src/test/java/")[-1].replace(".java", "").replace("/", ".")
    )
    test_case = f"{classname}#{methodname}"
    module = changed_test.split("src/test/java/")[0]
    if module.endswith("/"):
        module = module[:-1]
    logger.info(f"Test class: {classname}")

    repo: UpdateRepo = setup_repo(
        exp["repo_name"], exp["commit_tgt"], repo_base=REPO_BASE
    )

    #  substitute with prediction
    pred = exp["test_gen"]
    substitute_code(repo, exp, pred)
    # import new imports
    imports = exp.get("imports_gen")
    if imports:
        add_imports(repo, exp, imports)

    os.chdir(repo_root)
    original_path = os.environ.get("PATH")

    os.environ["JAVA_HOME"] = java_dict[exp["tgt_java_version"]]
    os.environ["PATH"] = os.environ["JAVA_HOME"] + "/bin:" + os.environ["PATH"]
    os.environ["MAVEN_HOME"] = mvn_dict[exp["tgt_maven_version"]]
    os.environ["PATH"] = os.environ["MAVEN_HOME"] + "/bin:" + os.environ["PATH"]

    if exp["repo_name"] == "Aiven-Open/klaw" or exp["repo_name"] == "shred/acme4j":
        cmd = [
            "mvn",
            "-T2C",
            "clean",
            "org.jacoco:jacoco-maven-plugin:0.8.9:prepare-agent",
            f"-Dtest={classname}",
            "test",
            "org.jacoco:jacoco-maven-plugin:0.8.9:report",
        ]

    elif exp["repo_name"] == "prebid/prebid-server-java":
        cmd = [
            "mvn",
            "-T2C",
            "clean",
            f"-Dtest={classname}",
            "test",
            "org.jacoco:jacoco-maven-plugin:0.8.9:report",
        ]

    else:
        cmd = ["mvn", "-T2C", "clean", "test", f"-Dtest={classname}"]

    if module:
        cmd = cmd[:2] + ["-pl", f"{module}", "--also-make"] + cmd[2:]
    cmd.extend(MVN_SKIPS)
    logger.info(" ".join(cmd))
    try:
        # mvn test
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600  # 10 min
        )
        output = proc.stdout.decode()
        lines = output.splitlines()
        test_info = [line for line in lines if "Tests run" in line]
        build_info = [line for line in lines if "BUILD SUCCESS" in line]
        error_info = [line for line in lines if "[ERROR]" in line]
        cannot_find_symbol = [
            line for line in error_info if "cannot find symbol" in line
        ]
        logger.info(f"================{exp['test_id']}==================")
        logger.info(test_info)
        logger.info(build_info)
        logger.info(error_info)
        logger.info("\n")

        if len(build_info) > 0:
            test_pass.append(exp["test_id"])
            build_pass.append(exp["test_id"])
        elif len(test_info) > 0:
            build_pass.append(exp["test_id"])
        if len(cannot_find_symbol) > 0:
            import_error.append(exp["test_id"])

        if proc.returncode == 0:
            jacoco_csv_path = os.path.join(
                repo_root, f"{module}", "target/site/jacoco/jacoco.csv"
            )
            print(jacoco_csv_path)
            if not os.path.exists(jacoco_csv_path):
                logger.info("Jacoco.csv do not exists!")
                output_csv.append([])
            else:
                with open(jacoco_csv_path, "r") as f:
                    df = pd.read_csv(f)
                    line = df[df["CLASS"] == prod_class]
                    if len(line) > 0:
                        output_csv.append(line.to_numpy()[0])
                        line_csv = ",".join(map(str, line.to_numpy()[0]))
                        logger.info(f"The coverage data: {line_csv}")
                    else:
                        logger.info("Fail to find prod class in CSV file!")
                        output_csv.append([])
        else:
            output_csv.append([])
        logger.info("\n")
        # reset
        os.environ["PATH"] = original_path
        git_reset = subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(git_reset.stdout.decode())

    except subprocess.TimeoutExpired:
        logger.info("Execute timeout.")
        raise
    except Exception as e:
        logger.error(e)
        raise

    return proc.returncode, error_info, test_info


def main(input_file: str):
    repo_name = input_file.split(".")[0].removeprefix("verified_")
    logger = MyLogger(timezone=TIME_ZONE)
    logger.set_log_file(os.path.join(FILE_BASE, f"logs/eval/{repo_name}.log"), "a")

    output_csv = []
    build_pass = []
    test_pass = []
    import_error = []

    with open(os.path.join(INPUT_BASE, input_file), "r") as f:
        all_outputs = json.load(f)

    # evaluate
    for idx in range(0, len(all_outputs)):
        try:
            build_test(
                all_outputs[idx],
                build_pass,
                test_pass,
                import_error,
                output_csv,
                logger,
            )
        except Exception as e:
            logger.error(e)
            raise

    logger.info(input_file)
    logger.info(
        f"===============TEST PASS : {len(test_pass)}=====================\n{test_pass}"
    )
    logger.info(
        f"===============BUILD PASS : {len(build_pass)}=====================\n{build_pass}"
    )
    logger.info(
        f"===============IMPORT ERROR : {len(import_error)}=====================\n{import_error}"
    )

    return build_pass, test_pass, import_error, output_csv


if __name__ == "__main__":
    files = [
        f
        for f in os.listdir(INPUT_BASE)
        if f.startswith("verified") and f.endswith(".json")
    ]
    files = sorted(files)
    print(files)

    with multiprocessing.Pool(processes=len(files)) as pool:
        results = pool.map(main, files)

    cov_result = []
    eval_result = []
    for idx, result in enumerate(results):
        build_pass, test_pass, import_error, oc = result
        repo_name = files[idx].split(".")[0].removeprefix("verified_")
        tj = {
            "repo_name": repo_name,
            "num_test_pass": len(test_pass),
            "test_pass": test_pass,
            "num_build_pass": len(build_pass),
            "build_pass": build_pass,
        }
        eval_result.append(tj)
        cov_result.extend(oc)

    os.chdir(FILE_BASE)

    # save result
    with open("eval_result.json", "w") as f:
        json.dump(eval_result, f, indent=4)

    # save csv file
    df = pd.DataFrame(cov_result)
    df.to_csv(csv_file_path, mode="w", index=False, header=False, encoding="utf-8-sig")
    print(f"CSV saved: {csv_file_path}")
