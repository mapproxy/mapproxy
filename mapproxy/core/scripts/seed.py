import signal
from mapproxy.core.seed import seed_from_yaml_conf, TileSeeder

def load_config(conf_file=None):
    if conf_file is not None:
        from mapproxy.core.config import load_base_config
        load_base_config(conf_file)

def set_service_config(conf_file=None):
    if conf_file is not None:
        from mapproxy.core.config import base_config
        base_config().services_conf = conf_file

def stop_processing(_signal, _frame):
    print "Stopping..."
    TileSeeder.stop_all()
    return 0

def main():
    from optparse import OptionParser
    usage = "usage: %prog [options] seed_conf"
    parser = OptionParser(usage)
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")
    parser.add_option("-f", "--proxy-conf",
                      dest="conf_file", default=None,
                      help="proxy configuration")
    parser.add_option("-s", "--services-conf",
                      dest="services_file", default=None,
                      help="services configuration")
    parser.add_option("-r", "--secure_rebuild",
                      action="store_true", dest="secure_rebuild", default=False,
                      help="do not rebuild tiles inplace. rebuild each level change"
                           " the level cache afterwards.")
    parser.add_option("-n", "--dry-run",
                      action="store_true", dest="dry_run", default=False,
                      help="do not seed, just print output")    
    
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error('missing seed_conf file as last argument')
    
    load_config(options.conf_file)
    set_service_config(options.services_file)
    
    signal.signal(signal.SIGINT, stop_processing)
    
    seed_from_yaml_conf(args[0], verbose=options.verbose,
                        rebuild_inplace=not options.secure_rebuild, 
                        dry_run=options.dry_run)

