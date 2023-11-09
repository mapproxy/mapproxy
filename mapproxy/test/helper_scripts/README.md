# pytest testing

after running scripts in mapproxy/test/helper_scripts/*bootstrap.sh you can test all redis with

```
MAPPROXY_TEST_REDIS_AUTH=localhost:6381 MAPPROXY_TEST_REDIS=localhost:6379 MAPPROXY_TEST_REDIS_TLS=localhost:6380 pytest mapproxy/test/unit/test_cache_redis.py
```