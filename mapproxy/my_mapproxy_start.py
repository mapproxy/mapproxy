import os
import mapproxy.wsgiapp
if __name__ == '__main__':
    os.chdir('C:\Users\Striar.Yunis\Documents\mymapproxy')
    mapproxy.wsgiapp.make_wsgi_app(services_conf='mapproxy.yaml', debug=True, ignore_config_warnings=True, reloader=False)
