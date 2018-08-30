import os, requests, json, time


API_TOKEN = os.getenv("CIRCLE_TOKEN")
assert API_TOKEN, "CIRCLE_TOKEN env variable is not set!"


def trigger_and_wait_for_build(max_time=300, poll_freq=8, project='cilantro', org='lamden', branch='master',
                               env_vars: dict=None):
    build_num = trigger_build(project=project, org=org, branch=branch, env_vars=env_vars)
    poll_for_build(build_num=build_num, max_time=max_time, poll_freq=poll_freq, project=project, org=org)


def poll_for_build(build_num: int, max_time=300, poll_freq=8, project='cilantro', org='lamden'):
    start = time.time()
    succ = False
    while max_time > 0:
        status = _get_build_status(build_num=build_num, project=project, org=org)['status']

        if status == 'success':
            succ = True
            break

        print("Build num {} has status {} that is not success yet. Waiting {} before next retry."
              .format(build_num, status, poll_freq))
        time.sleep(poll_freq)
        max_time -= poll_freq

    duration = round(time.time() - start, 2)
    if succ:
        print("[SUCCESS] Build number {} succeeded in {} seconds.".format(build_num, duration))
    else:
        print("[FAILURE] Build number {} did not succeeded after {} seconds".format(build_num, duration))


def trigger_build(project='cilantro', org='lamden', branch='master', env_vars: dict=None) -> int:
    url = "https://circleci.com/api/v1.1/project/github/{org}/{project}/tree/{branch}?circle-token={token}"\
        .format(org=org, project=project, branch=branch, token=API_TOKEN)

    r = requests.post(url, data={'build_parameters': env_vars})
    json_reply = json.loads(r.content.decode('utf-8'))
    return json_reply['build_num']


def _get_build_status(build_num: int, project='cilantro', org='lamden') -> dict:
    url = "https://circleci.com/api/v1.1/project/github/{org}/{project}/{build_num}?circle-token={token}"\
        .format(org=org, project=project, build_num=build_num, token=API_TOKEN)

    r = requests.get(url)
    return json.loads(r.content.decode('utf-8'))


if __name__ == '__main__':
    # build_num = trigger_build('cilantro')
    # broken is 675, working is 662
    # _get_build_status(662)
    # print(check_build_success(675))
    # poll_for_build(675, max_time=12, poll_freq=4)
    trigger_and_wait_for_build(max_time=20, poll_freq=5, branch='dev2-delegate-block-manager', env_vars={'SENECA_BRANCH': '644f27b2dff1c310d81f409d96121d80e48745a8'})
