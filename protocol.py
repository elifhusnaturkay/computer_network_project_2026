"""
protocol.py
-----------
Mesaj oluşturma, gönderme ve alma yardımcı fonksiyonları.
Helper functions for creating, sending, and receiving messages.

Protokol formatı / Protocol format:
  - Her mesaj bir JSON nesnesidir, satır sonu ile biter (\n)
  - Each message is a JSON object terminated by a newline (\n)

Mesaj yapısı / Message structure:
  {
    "type":   str,   # mesaj türü / message type
    "sender": str,   # gönderenin kullanıcı adı / sender's username
    "data":   dict   # mesaja özgü ek bilgiler / message-specific payload
  }
"""

import json


def make_message(msg_type: str, sender: str, data: dict) -> dict:
    """
    Standart mesaj sözlüğü oluşturur.
    Creates a standard message dictionary.

    Parametreler / Parameters:
      msg_type : Mesaj türü (ör. "chat", "group_msg") / Message type (e.g. "chat", "group_msg")
      sender   : Gönderenin kullanıcı adı / Sender's username
      data     : Türe özgü ek veri / Type-specific payload dict
    """
    return {
        "type": msg_type,
        "sender": sender,
        "data": data,
    }


def send_msg(sock, msg_dict: dict) -> None:
    """
    Mesajı JSON olarak kodlar ve sokete gönderir.
    Encodes the message as JSON and sends it over the socket.

    Satır sonu (\n) mesajların sınırını belirler.
    The newline (\n) acts as the message delimiter.
    """
    # JSON'a dönüştür ve satır sonu ekle / Convert to JSON and append newline
    line = json.dumps(msg_dict) + "\n"
    # UTF-8 olarak kodla ve gönder / Encode as UTF-8 and send
    sock.sendall(line.encode("utf-8"))


def recv_msg(file_obj):
    """
    Soketin dosya nesnesiyle bir satır okur ve JSON mesajı döner.
    Reads one line from the socket file object and returns the parsed JSON message.

    Bağlantı kapandıysa None döner.
    Returns None if the connection is closed.
    """
    line = file_obj.readline()

    # Boş satır → bağlantı kapandı / Empty line → connection closed
    if not line:
        return None

    # JSON ayrıştır ve döndür / Parse JSON and return
    return json.loads(line.strip())
