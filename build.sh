#!/bin/bash

version=$1
no_cache=$2
push=$3

if [ -n "$version" ]; then
    if [ "$no_cache" == "nc" ]; then
        echo "Building v$version with no cache"
        docker build -t vmlc-api:$version . --no-cache
    else
        echo "Building v$version with cache"
        docker build -t vmlc-api:$version .
    fi
    
    if [ $? -eq 0 ]; then
        echo "Built! Now tagging to repo..."
        docker tag vmlc-api:$version theolujay/vmlc-api:$version
        
        if [ "$push" == "p" ]; then
            echo "Pushing v$version to repo -> theolujay/vmlc-api"
            docker push theolujay/vmlc-api:$version
            echo "Pushed to repo!"
        else
            echo "Not yet pushed to repo"
        fi
    else
        echo "Build failed!"
        exit 1
    fi
else
    echo "No version provided - building with 'latest'..."
    docker build -t vmlc-api:latest .
    echo "Built as 'vmlc-api:latest'"
fi