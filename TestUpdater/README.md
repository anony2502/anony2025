### Introduction

1. **Check ./repos for information of cloning the repos for evaluation**
2. **Set file paths in `utils/configs.py`**, including the Java and Maven environment paths (absolute paths are required) and the model `API_KEY`.
3. **Configure the `base_url` for each model** in `utils/llm.py`.
4. **Run `python pipeline.py -m modelname` to reproduce the experiments.**

   * Replace `modelname` with one of the available models such as `llama`, `gpt41`, `gpt4omini`, `deepseek`, etc.
   * See `pipeline.py` for the modelnames.
5. **Configure and run `python eval.py` to evaluate the results.**
6. **Run `python cal_cover.py ***.csv` to calculate the overall coverage rate.**

### Replication
1. Run `RQ12.sh` to reproduce our RQ1 and RQ2. You can evaluate the experimental results using `eval.py`. The evaluation results will be generated in the `logs` directory, and the test coverage CSV files will be generated in the `coverage` directory. The script `cal_cover.py` is used to calculate the overall coverage. To compare the test coverage of two individual methods, please refer to `coverage/compare.ipynb`.

2. Run `RQ3` to reproduce our RQ3, and evaluate the compilation and test pass rates using `eval.py`.

3. We provide the datasets used by the baseline methods in `data/baselines`.
