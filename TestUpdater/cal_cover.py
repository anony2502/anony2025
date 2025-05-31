import argparse, os
import pandas as pd
from utils.logger import logger
from utils.configs import FILE_BASE
logger.set_log_file("logs/cal_cover.log", "a")

def cal_cover(df):
    branch_cov_list = []
    line_cov_list = []
    test_pass = 0
    
    for idx, row in df.iterrows():
        if pd.isna(row).all():
            branch_cov_list.append(0)
            line_cov_list.append(0)
        else:
            test_pass += 1
            # Calculate branch coverage
            branch_covered = row["BRANCH_COVERED"]
            branch_total = row["BRANCH_MISSED"] + row["BRANCH_COVERED"]
            branch_cov = branch_covered / branch_total if branch_total != 0 else 0
            
            # Calculate line coverage
            line_covered = row["LINE_COVERED"]
            line_total = row["LINE_MISSED"] + row["LINE_COVERED"]
            line_cov = line_covered / line_total if line_total != 0 else 0
            
            branch_cov_list.append(branch_cov)
            line_cov_list.append(line_cov)
    
    # Return test_pass count and sums of coverages
    return test_pass, sum(branch_cov_list), sum(line_cov_list)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str)
    args = parser.parse_args()
    csv_file = os.path.join(FILE_BASE, 'coverage', args.file)
    logger.info(f"====Starting processing file: {csv_file}====")

    column_names = "GROUP,PACKAGE,CLASS,INSTRUCTION_MISSED,INSTRUCTION_COVERED,BRANCH_MISSED,BRANCH_COVERED,LINE_MISSED,LINE_COVERED,COMPLEXITY_MISSED,COMPLEXITY_COVERED,METHOD_MISSED,METHOD_COVERED"
    column_names = column_names.split(',')

    df = pd.read_csv(csv_file, names=column_names, header=None)
    print(df)

    test_pass, total_branch_cov, total_line_cov = cal_cover(df)
    num = 195
    
    logger.info(f"===============test pass : {test_pass}=====================")
    logger.info(f"===============BRANCH COVERAGE : {total_branch_cov/num}=====================")
    logger.info(f"=={total_branch_cov}==")
    logger.info(f"===============LINE COVERAGE: {total_line_cov/num}=====================")
    logger.info(f"=={total_line_cov}==")