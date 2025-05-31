1. **Check ./repos for information of cloning the repos for evaluation**
2. **Set file paths in `utils/configs.py`**, including the Java and Maven environment paths (absolute paths are required) and the model `API_KEY`.
3. **Configure the `base_url` for each model** in `utils/llm.py`.
4. **Run `python pipeline.py -m modelname` to reproduce the experiments.**

   * Replace `modelname` with one of the available models such as `llama`, `gpt41`, `gpt4omini`, `deepseek`, etc.
   * See `pipeline.py` for the modelnames.
5. **Configure and run `python eval.py` to evaluate the results.**
6. **Run `python cal_cover.py ***.csv` to calculate the overall coverage rate.**