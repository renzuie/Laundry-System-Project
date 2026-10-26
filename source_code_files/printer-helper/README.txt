LABADA LINK - receipt printer helper (auto cut)
================================================

What it does
  The web page sends each receipt to this small program. It prints the receipt
  on the thermal printer and cuts the paper. If the program is not running,
  the page prints the normal way (browser print), so nothing breaks.

1) Install once
  Windows : pip install python-escpos pillow pywin32
  Pi      : sudo apt install python3-pip libusb-1.0-0
            pip3 install python-escpos pillow --break-system-packages

2) Edit config.json
  Windows : "printer": { "type": "windows", "name": "Caysn58-2" }
  Pi (USB): "printer": { "type": "usb", "vid": "0x0416", "pid": "0x5011" }     (see `lsusb`)
  Pi (dev): "printer": { "type": "file", "dev": "/dev/usb/lp0" }
  No printer yet (test only): "printer": { "type": "preview" }  -> saves pictures in the "preview" folder

  "paper_dots": 384 for 58 mm paper, 576 for 80 mm paper
  "cut": "feed_partial" (feeds to the blade then partial cut - recommended)
         "partial" | "full" | "none"
         for partial/full, "feed_lines" blank lines are fed first
  "allowed_origins": the website address(es) that may print. Keep your Cloudflare address in it.

3) Run it
  Windows : double-click start_helper.bat      (leave the window open)
  Pi      : python3 print_helper.py

  Start automatically
  Windows : press Win+R, type shell:startup, put a shortcut to start_helper.bat there
  Pi      : add this line to the autostart file (same file you used for Chromium):
            @python3 /home/pi/printer-helper/print_helper.py

4) Quick check
  Open  http://127.0.0.1:5000/ping  in a browser -> {"ok": true, ...}

Notes
  - Printing goes to this computer only (127.0.0.1); other devices cannot reach it.
  - New Chrome/Chromium may ask once: "Look for and connect to devices on your local network".
    Click Allow. (For the Pi kiosk you can pre-allow it with the policy
    "LocalNetworkAccessAllowedForUrls": ["https://labada-link.cvsu.workers.dev"] in the same
    /etc/chromium/policies/managed/ file as the print settings.)
  - With the helper running you do not need --kiosk-printing for receipts. Keep it for the report print.
  - Pi USB permission error? Run once with sudo to test, or add the user to the "lp" group:
    sudo usermod -aG lp $USER   (then log out and in)
