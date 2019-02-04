branch=$(git branch | grep \* | cut -d ' ' -f2)

commitHash=$(git rev-parse HEAD)
commitHash=${commitHash:0:8}

dirHash=$(python3  ops/tools/cilantrohasher.py)
dirHash=${dirHash:0:8}

remoteTag="$branch-$commitHash"
localTag="$branch-$commitHash-$dirHash"

echo "--------------------------------------------"
echo "Building docker images with..."
echo "branch $branch"
echo "commitHash $commitHash"
echo "dirHash $dirHash"
echo "localTag $localTag"
echo "remoteTag $remoteTag"
echo "--------------------------------------------"

echo "--------------------------------------------"
echo "Building base image..."
docker build -t lamden/cilantro_base:$localTag -f docker/cilantro_base .

echo "--------------------------------------------"
echo "Building light image..."
docker build  --cache-from lamden/cilantro_base:$localTag -t lamden/cilantro_light:$localTag -f docker/cilantro_light .

echo "--------------------------------------------"
echo "Building full image..."
docker build  --cache-from lamden/cilantro_base:$localTag -t lamden/cilantro_full:$localTag -f docker/cilantro_full .

docker tag lamden/cilantro_light:$localTag lamden/cilantro_light:$remoteTag
docker tag lamden/cilantro_full:$localTag lamden/cilantro_full:$remoteTag

if [ "$1" = "--push" ]
then
    echo "Pushing docker images..."
    docker push lamden/cilantro_light:$localTag
    docker push lamden/cilantro_full:$localTag
fi
