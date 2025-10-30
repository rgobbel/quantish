#!/usr/bin/env bash

models=(
  fig44
  fig45
  fig46
  fig47
  fig48
  fig49
  fig411
  fig412
  fig413
  fig414
  fig415
  fig416
)

for model in "${models[@]}"; do
  echo $model, numeric...
  python -m quantish.main --numeric --add-with-signs --config models/${model}.yaml --log logs/${model}_numeric.log --diagram mermaid/${model}_numeric.mmd
done
for model in "${models[@]}"; do
  echo $model, symbolic...
  python -m quantish.main --symbolic --add-with-signs --config models/${model}.yaml --log logs/${model}_symbolic.log --diagram mermaid/${model}_symbolic.mmd
done
