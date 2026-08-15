# Quantish Physics

A simulation of "quantish" physics, as described in Chapter 4 of *Good and Real: Demystifying Paradoxes from Physics to Ethics* (Gary L. Drescher, 2006).

### bulleted
- normalize
  - weights
  - values

```
usage: main.py [-h] -c CONFIG [-s | --simulate | --no-simulate] [-d DIAGRAM] [--diagram-when {before,after,both}] [-l LOG] [--loglevel {debug,info,warning,error}]
               [--preserve-log] [--symbolic] [--numeric] [--use-common | --no-use-common]
               [--sample | --no-sample] [--n-samples N_SAMPLES] [--epr-stats] [--full-stats]

options:
  -h, --help            show this help message and exit
  -c, --config CONFIG   Path to YAML configuration file (default: None)
  -s, --simulate, --no-simulate
                        Run simulation (default: True)
  -d, --diagram DIAGRAM
                        Create a Mermaid diagram of the gate network on the named file, extension '.mmd' (default: None)
  --diagram-when {before,after,both}
                        When to create a diagram, before or after simulation (default: after)
  -l, --log LOG         Log file (default: None)
  --loglevel {debug,info,warning,error} (default: info)
  --preserve-log        Preserve existing log file. Default is to wipe it out and start over (default: False)
  --symbolic            Force symbolic math
  --numeric             Force numeric math
  --use-common, --no-use-common
                        Load values from common.yaml before individual model files (default: use-common)
  --sample, --no-sample
                        Take gate outputs as distributions, run with one random sample (default: no-sample)
  --n-samples N_SAMPLES
                        Run this many sample executions, collect statistics on results (default: 1)
  --epr-stats           Run statistics on EPR experiment model (book figures 4.16 and 4.17) (default: False)
  --full-stats          Include particle names and probabilities in results (default: False)
```