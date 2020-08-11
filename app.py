#!/usr/bin/python

import os
from TraefikUpdater import TraefikUpdater

def main():
    updater = TraefikUpdater()
    updater.process_containers()

    # This blocks
    updater.enter_update_loop()

if __name__ == "__main__":
    main()