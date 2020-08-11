# traefik-cloudflare-updater

Instead of using a wildcard DNS record, create records dynamically using this.

Only works with traefikv2 configuration, look at the above repo for v1 support.

When you run the container, it'll update all the DNS records it can find, afterward it will sit and wait for any new traefik enabled containers to start and then updtae them. If this container restarts, it'll re-update everything.

Idea taken from the following GitHub repo: https://github.com/tiredofit/docker-traefik-cloudflare-companion


 ## Why write this, and not use the above repo?

I didn't like the following things (just my preference):
* No updating of existing records
* No exclusions
* Python 2
* Stuff not needed for the operation of this service within the container
* Bash and python mix

What I did like:
* The general idea, wildcard domains are not nice
* The fact it's at least in python
* The elegant usage of docker events to update new containers
  
## Usage
Example `docker-compose.yml` service:

```yml
dnsupdater:
image: dchidell/traefik-cloudflare-updater
restart: unless-stopped
volumes:
- /var/run/docker.sock:/var/run/docker.sock:ro
environment:
- CF_EMAIL=email@example.com
- CF_TOKEN=1234567890
- TARGET_DOMAIN=example.com
- DOMAIN1=mydomain1.com
- DOMAIN1_ZONE_ID=1234567890
- DOMAIN2=mydomain2.com
- DOMAIN2_ZONE_ID=1234567890
- EXCLUDED_DOMAINS=static.mydomain1.com,test.mydomain2.com
```


### Mandatory ENV vars:

`TARGET_DOMAIN` - a CNAME will be created pointing to this target

`CF_EMAIL` - CloudFlare API Email

`CF_TOKEN` - CloudFlare API Token

`DOMAIN#` - Multiple of these per domain, e.g. `DOMAIN1=example.com`, `DOMAIN2=example.net` ... `DOMAINn=example.org`

`DOMAIN#_ZONE_ID` - CloudFlare zone ID for domain index.



### Optional ENV vars:

`DOMAIN#_PROXIED` - Whether to use CloudFlare proxy. Should be 'TRUE' or 'FALSE' (not 1 or 0) (defaults to TRUE)

`EXCLUDED_DOMAINS` - Comma separated domains to be excluded from updating (i.e. if you want to statically define something) e.g. `EXCLUDED_DOMAINS=sub.domain.com,sub2.domain.com`