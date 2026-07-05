#!/bin/bash
export VERSION
VERSION=$(cat "$(dirname "$0")/VERSION")

export REPO_URL
REPO_URL=$(git -C "$(dirname "$0")" remote get-url origin 2>/dev/null \
  | sed 's/^git@github\.com:/https:\/\/github.com\//' \
  | sed 's/\.git$//')

export PROJECT_NAME
PROJECT_NAME="AI Status"
