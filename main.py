import sys
import pjsua as pj
import threading
import time
import wave
import ConfigParser
from os import listdir
from os.path import isfile, join, splitext

# Globals
current_call = None
lut_times = dict()
prolog_slot = None
prolog_pl = None
choice = None
number = ""

# Configuration variables
CONF_FILE = './sip.conf'
SND_DIR = './snds'

def log_cb(level, str, len):
    print str,
    sys.stdout.flush()

class MyAccountCallback(pj.AccountCallback):
    sem = None

    def __init__(self, account):
        pj.AccountCallback.__init__(self, account)

    def wait(self):
        self.sem = threading.Semaphore(0)
        self.sem.acquire()

    def on_reg_state(self):
        if self.sem:
            if self.account.info().reg_status >= 200:
                self.sem.release()

    # Notification on incoming call
    def on_incoming_call(self, call):
        global current_call 
        global prolog_slot
        global prolog_pl
        global choice
        global number
        lib = pj.Lib.instance()
        
        # Reject if busy
        if current_call:
            call.answer(486, "Busy")
            return

        # Set up callbacks
        choice = None
        number = ""
        current_call = call
        call_cb = MyCallCallback(current_call)
        current_call.set_callback(call_cb)
        # Let the phone ring
        current_call.answer(180)
        print "ANSWER", call.info().remote_uri
        # Wait for appromimately 1 ring
        time.sleep(2)
        # Answer the phone!
        current_call.answer(200)
        # Wait a little bit
        time.sleep(1)
        # Start the prologue
        prolog_pl = lib.create_player(join(SND_DIR, 'prolog.wav'), loop = False)
        prolog_slot = lib.player_get_slot(prolog_pl)
        lib.conf_connect(prolog_slot, call.info().conf_slot)

class MyCallCallback(pj.CallCallback):
    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)
        self.media_active = False

    def on_dtmf_digit(self, digit):
        global prolog_slot
        global prolog_pl
        global choice
        global number
        lib = pj.Lib.instance()

        # Make sure the prologue stops playing
        if prolog_slot != None:
          lib.conf_disconnect(prolog_slot, self.call.info().conf_slot)
          lib.player_destroy(prolog_pl)
          prolog_slot = prolog_pl = None

        if choice is None:
          if digit.isdigit():
            num = int(digit)
            if num == 1:
              print('Hexadecimal')
              choice = 1
            elif num == 0:
              print('Binary')
              choice = 0
            else:
              print('{}'.format(num))
              choice = None
        else:
          # Check if we received a '#', if so, we can convert
          if chr(ord(digit)) == '#':
            num = int(number)

            if choice == 1:
              # Perform hexadecimal conversion
              result = format(num, 'x')
            elif choice == 0:
              # Perform binary conversion
              result = format(num, 'b')

            digits = list(result)
            print ("Hexadecimal" if choice == 1 else "Binary"), digits
            digits_files = map(lambda x: join(SND_DIR, x + '.wav'), digits)
            d_pl = lib.create_playlist(digits_files, 'digits', False)
            d_slot = lib.playlist_get_slot(d_pl)
            lib.conf_connect(d_slot, self.call.info().conf_slot)
            playtime = sum(lut_times[x] for x in digits)
            time.sleep(playtime)
            lib.playlist_destroy(d_pl)

            # Start the epilogue, wait, and hang up
            time.sleep(0.5)
            epilog_pl = lib.create_player(join(SND_DIR, 'epilog.wav'), loop = False)
            lib.conf_connect(lib.player_get_slot(epilog_pl), self.call.info().conf_slot)
            time.sleep(lut_times['epilog'] + 0.5)
            self.call.hangup()
          else:
            # Not yet received a '#' so
            number += digit
            print('{}'.format(number))

    def on_state(self):
        global current_call
        print "STATE", self.call.info().state_text,
        print "CODE", self.call.info().last_code, 
        print self.call.info().last_reason

        if self.call.info().state == pj.CallState.DISCONNECTED:
            current_call = None

    def on_media_state(self):
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            # Connect the call to sound device
            call_slot = self.call.info().conf_slot
            lib = pj.Lib.instance()
            lib.conf_connect(call_slot, 0)
            lib.conf_connect(0, call_slot)
            if self.call.info().state != pj.CallState.CONFIRMED:
                print "MEDIA active, but not confirmed"
            elif not self.media_active:
                lib.set_snd_dev(0, 0)
                print "MEDIA active"
                self.media_active = True
            else:
                print "MEDIA already active"
        else:
            self.media_active = False
            print "MEDIA inactive"

lib = pj.Lib()

try:
    # Calculate LUT with seconds of play time for each digit file
    for f in listdir(SND_DIR):
      if isfile(join(SND_DIR, f)):
        wfile = wave.open(join(SND_DIR, f))
        lut_times[splitext(f)[0]] = (1.0 * wfile.getnframes()) / wfile.getframerate()
        wfile.close()

    # Read configuration
    config = ConfigParser.ConfigParser()
    config.readfp(open(CONF_FILE))

    # Initialize SIP library
    lib.init(log_cfg=pj.LogConfig(console_level=1, callback=log_cb))
    lib.create_transport(pj.TransportType.UDP, pj.TransportConfig(5060))
    lib.set_null_snd_dev()
    lib.start()
    lib.handle_events()

    # Initialize and connect account
    acc_cfg = pj.AccountConfig()
    acc_cfg.id = config.get('sip', 'id')
    acc_cfg.reg_uri = config.get('sip', 'reg_uri')
    acc_cfg.proxy = [ config.get('sip', 'proxy') ]
    acc_cfg.auth_cred = [ pj.AuthCred("*", config.get('sip', 'auth_user'), config.get('sip', 'auth_pass')) ]
    acc = lib.create_account(acc_cfg)
    acc_cb = MyAccountCallback(acc)
    acc.set_callback(acc_cb)
    acc_cb.wait()
    print "Registration complete", acc.info().reg_status, acc.info().reg_reason
    
    # Infinite loop
    while True:
      time.sleep(1)

    # Pointless cleanup
    acc.delete()
    acc = None
    lib.destroy()
    lib = None

except pj.Error, e:
    print "Exception occurred: " + str(e)
    lib.destroy()
