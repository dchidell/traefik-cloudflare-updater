import os
import re
import time
import docker
import CloudFlare

__author__ = "David Chidell"

class TraefikUpdater:
    def __init__(self):
        self.target_domain = os.environ['TARGET_DOMAIN']
        excluded = os.environ.get('EXCLUDED_DOMAINS')
        if excluded is None:
            self.excluded_domains = []
        else:
            self.excluded_domains = excluded.split(',')

        self.tld_info = {}
        self.get_domain_vars()

        self.host_pattern = re.compile('\`([a-zA-Z0-9\.]+)\`')

        self.cf = CloudFlare.CloudFlare(email=os.environ['CF_EMAIL'] , token=os.environ['CF_TOKEN'])
        self.dkr = docker.from_env()

    def enter_update_loop(self):
        print(f'Listening for new containers...')
        t = int(time.time())
        for event in self.dkr.events(since=t, filters={'status': 'start'}, decode=True):
            if event.get('status') == 'start':
                try:
                    container = self.dkr.containers.get(event.get('id'))
                except docker.errors.NotFound as e:
                    pass
                else:
                    if container.labels.get("traefik.enable",'False').upper() == "TRUE":
                        print(f'New container online: {container.name}, processing...')
                        self.process_container(container)
        
    def process_containers(self):
        containers = self.dkr.containers.list(filters={"status":"running","label":"traefik.enable=true"})
        print(f'Found {len(containers)} existing containers to process')
        for container in containers:
            self.process_container(container)
        print(f'Finished bulk updating containers!')

    def process_container(self,container):
        for label, value in container.labels.items():
            if 'rule' in label and 'Host' in value:
                domains = self.host_pattern.findall(value)
                print(f'Found domains: {domains} for container: {container.name}')
                for domain in domains:
                    self.update_domain(domain)
                                     
    def update_domain(self,domain):
        dom_split = domain.split('.')
        if len(dom_split) >= 3:
            tld = '.'.join(dom_split[1:])
        else:
            tld = domain

        if self.tld_info.get(tld) is None:
            print(f'TLD {tld} not in updatable list')
            return False

        dom_info = self.tld_info[tld]
        common_dict = {i: dom_info[i] for i in ('type', 'content', 'proxied')}
        post_dict = {**{'name':domain},**common_dict}
        try:
            get_records = self.cf.zones.dns_records.get(dom_info['zone'], params={'name':domain})
            if len(get_records) == 0:
                post_record = self.cf.zones.dns_records.post(dom_info['zone'], data=post_dict)
                print(f'New record created: {domain}')
            else:
                for record in get_records:
                    post_record = self.cf.zones.dns_records.put(dom_info['zone'], record['id'], data=post_dict)
                    print(f'Existing record updated: {domain}')

        except CloudFlare.exceptions.CloudFlareAPIError as e:
            print(f'API call failed: {str(e)}')
            return False
        return True

    def get_domain_vars(self):
        tld_count = 0
        self.tld_info = {}
        while True:
            tld_count += 1
            try:
                domain = os.environ[f'DOMAIN{tld_count}']
                zone = os.environ[f'DOMAIN{tld_count}_ZONE_ID']
                try:
                    proxied = os.environ.get(f'DOMAIN{tld_count}_PROXIED',"TRUE").upper() == 'TRUE'
                except KeyError:
                    proxied = false
                self.tld_info[domain] = {"zone":zone, "proxied":proxied, "type":"CNAME", "content":self.target_domain}
            except KeyError:
                break
        print(f'Found {tld_count-1} TLDs! {self.tld_info}')
