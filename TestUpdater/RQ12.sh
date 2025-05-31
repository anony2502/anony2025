#!/bin/bash
python pipeline.py -m gpt41
python pipeline.py -m llama
python pipeline.py -m deepseek

# RUN naivellm.py
for i in {1..7}
do
    python naivellm.py --file $i
done
