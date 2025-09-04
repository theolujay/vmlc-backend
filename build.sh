#!/bin/bash

version=$1
no_cache=$2
push=$3

if [ -n "$version" ]; then
    if [ "$no_cache" == "nc" ]; then
        echo "Building v$version with no cache"
        docker build -t vmlc-backend:$version . --no-cache
    else
        echo "Building v$version with cache"
        docker build -t vmlc-backend:$version .
    fi
    
    if [ $? -eq 0 ]; then
        echo "Built! Now tagging to repo..."
        docker tag vmlc-backend:$version theolujay/vmlc-backend:$version
        
        if [ "$push" == "p" ]; then
            echo "Pushing v$version to repo -> theolujay/vmlc-backend"
            docker push theolujay/vmlc-backend:$version
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
    docker build -t vmlc-backend:latest .
    echo "Built as 'vmlc-backend:latest'"
fi