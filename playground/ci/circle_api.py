import os, requests, json


API_TOKEN = os.getenv("CIRCLE_TOKEN")


def trigger_build(project='cilantro', org='lamden', branch='master') -> int:
    url = "https://circleci.com/api/v1.1/project/github/{org}/{project}/tree/{branch}?circle-token={token}"\
        .format(org=org, project=project, branch=branch, token=API_TOKEN)

    print("Posting to URL {}".format(url))

    r = requests.post(url)

    json_reply = json.loads(r.content.decode('utf-8'))
    print("got dat request {} with dat json\n{}".format(r, json_reply))
    build_num = json_reply['build_num']


def get_build_status(build_num: int, project='cilantro', org='lamden') -> dict:
    url = "https://circleci.com/api/v1.1/project/github/{org}/{project}/{build_num}"\
        .format(org=org, project=project, build_num=build_num)

    print("getting from url {}".format(url))

    r = requests.get(url)

    print("got dat reply {}".format(r))


if __name__ == '__main__':
    # build_num = trigger_build('cilantro')
    get_build_status(675)