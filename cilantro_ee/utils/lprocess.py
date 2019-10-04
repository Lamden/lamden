from cilantro_ee.core.logger.base import get_logger
from multiprocessing import Process
import traceback, os, cProfile, pkg_resources, json
from vprof import runner


DELIM_LEN = 60
OUTER_DELIM = '!'
INNER_DELIM = '-'


class LProcess(Process):
    def run(self):
        log = get_logger(self.name)
        log.info("---> {} Starting --->".format(self.name))
        profiling = os.getenv('PROFILING', '')
        vprof_options = set('cmph').intersection(set(profiling))
        testname = os.getenv('TEST_NAME', 'sample_test')
        testid = os.getenv('TEST_ID', '')
        nodename = 'node'# os.getenv('HOST_NAME', 'node')
        profdir = os.path.join('profiles', testname, testid, nodename)
        profpath = os.path.join(profdir, self.name)
        try:
            # First create this directory for profiling
            if not os.path.exists(profdir) and profiling:
                os.makedirs(profdir)
            # Profiling with gprof to create Node graph profile
            if 'n' in profiling:
                pr = cProfile.Profile()
                pr.enable()
                super().run()
                pr.create_stats()
                pr.dump_stats('{}.stats'.format(profpath))
            # Profiling with vprof to create visualizations as specified in vprof_options
            elif len(vprof_options) > 0:
                vprof_options = ''.join(vprof_options)
                run_stats = runner.run_profilers((super().run, [], {}), vprof_options)
                with open('{}.json'.format(profpath), 'w+') as f:
                    run_stats['version'] = pkg_resources.get_distribution("vprof").version
                    f.write(json.dumps(run_stats))
            else:
                super().run()
        except Exception as e:
            err_msg = '\n' + OUTER_DELIM * DELIM_LEN
            err_msg += '\nException caught on ' + self.name + ':\n' + str(e)
            err_msg += '\n' + INNER_DELIM * DELIM_LEN
            err_msg += '\n' + traceback.format_exc()
            err_msg += '\n' + INNER_DELIM * DELIM_LEN
            err_msg += '\n' + OUTER_DELIM * DELIM_LEN
            log.error(err_msg)
        finally:
            log.info("<--- {} Terminating <---".format(self.name))
            # TODO -- signal to parent to call .join() on this process and clean up nicely
