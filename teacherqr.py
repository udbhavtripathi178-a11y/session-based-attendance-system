import qrcode
from datetime import datetime

sessioncode = datetime.now().strftime("%Y%m%d%H%M")

qr = qrcode.make(sessioncode)
qr.save("classqr.png")

print("QR generated successfully")
print("Session code:", sessioncode)
print("classqr.png screen par dikhao")
