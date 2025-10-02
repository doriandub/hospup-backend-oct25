#!/bin/bash

# AWS CLI Wrapper - Utilise le chemin complet vers AWS CLI
# Usage: ./aws-wrapper.sh [commandes aws normales]

AWS_CLI_PATH="/Users/doriandubord/Library/Python/3.9/bin/aws"

if [ ! -f "$AWS_CLI_PATH" ]; then
    echo "❌ AWS CLI non trouvé à $AWS_CLI_PATH"
    exit 1
fi

# Exécuter la commande AWS avec tous les arguments
$AWS_CLI_PATH "$@"