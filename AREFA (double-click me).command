#!/bin/bash
# Double-click launcher for AREFA. Runs the local workstation and opens it in
# your browser. Close this window to stop AREFA.
cd "$(dirname "$0")"
clear
python3 arefa_workstation.py
