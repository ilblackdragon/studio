"""Data providers."""
import os
import yaml
import pyhocon

from db_providers.local_db_provider import LocalDbProvider
from db_providers.s3_provider import S3Provider
from storage.storage_setup import setup_storage, get_storage_db_provider,\
    set_storage_verbose_level, get_artifact_store
from util import logs
from util.util import parse_verbosity

def get_config(config_file=None):

    config_paths = []
    if config_file:
        if not os.path.exists(config_file):
            raise ValueError('User config file {} not found'
                             .format(config_file))
        config_paths.append(os.path.expanduser(config_file))

    config_paths.append(os.path.expanduser('~/.studioml/config.yaml'))
    config_paths.append(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "default_config.yaml"))

    for path in config_paths:
        if not os.path.exists(path):
            continue

        with(open(path)) as f:
            if path.endswith('.hocon'):
                config = pyhocon.ConfigFactory.parse_string(f.read())
            else:
                config = yaml.load(f.read(), Loader=yaml.FullLoader)

                def replace_with_env(config):
                    for key, value in config.items():
                        if isinstance(value, str):
                            config[key] = os.path.expandvars(value)

                        elif isinstance(value, dict):
                            replace_with_env(value)

                replace_with_env(config)

            return config

    raise ValueError('None of the config paths {0} exists!'
                     .format(config_paths))

def get_db_provider(config=None, blocking_auth=True):

    db_provider = get_storage_db_provider()
    if db_provider is not None:
        return db_provider

    if config is None:
        config = get_config()
    verbose = parse_verbosity(config.get('verbose'))

    # Save this verbosity level as global for the whole experiment job:
    set_storage_verbose_level(verbose)

    logger = logs.getLogger("get_db_provider")
    logger.setLevel(verbose)
    logger.debug('Choosing db provider with config:')
    logger.debug(config)

    if 'storage' in config.keys():
        artifact_store = get_artifact_store(config['storage'])
    else:
        artifact_store = None

    assert 'database' in config.keys()
    db_config = config['database']
    if db_config['type'].lower() == 's3':
        db_provider = S3Provider(db_config,
                          blocking_auth=blocking_auth)
        if artifact_store is None:
            artifact_store = db_provider.get_storage_handler()

    elif db_config['type'].lower() == 'gs':
        raise NotImplementedError("GS is not supported.")

    elif db_config['type'].lower() == 'local':
        db_provider = LocalDbProvider(db_config,
                          blocking_auth=blocking_auth)
        if artifact_store is None:
            artifact_store = db_provider.get_storage_handler()

    else:
        raise ValueError('Unknown type of the database ' + db_config['type'])

    setup_storage(db_provider, artifact_store)
    return db_provider


