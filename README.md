# PS5 ELF Sender

صفحة تفتحها **على جهاز PS5 نفسه**، تضغط زر، والـ payload يشتغل.

**https://12lie20.github.io/ps5-elf-sender/**

## الأزرار

| الزر | وش يسوي |
|---|---|
| **Send to PS5** | يرسل `crlr69.elf` للـ `elfldr` على `127.0.0.1:9021` داخل الجهاز |
| **JB 13.60** | يفتح صفحة Relapse (استغلال WebKit + kernel) وتشغّله في نفس المتصفح |

## الأدوات (كلها بايلودات)

| الملف | من وين | وش يسوي |
|---|---|---|
| `kstuff.elf` | [EchoStretch/kstuff-lite](https://github.com/EchoStretch/kstuff-lite) v1.11 | تعديلات الكرنل، أساس تشغيل نسخ الالعاب |
| `shadowmountplus.elf` | [drakmor/ShadowMountPlus](https://github.com/drakmor/ShadowMountPlus) 1.7beta5fix1 | يركّب نسخ الالعاب (UFS/PFS) تلقائي |
| `etaHEN-2.5B.bin` | [etaHEN/etaHEN](https://github.com/etaHEN/etaHEN) 2.5B | صندوق أدوات HEN (ملفات، ثيمات، شروحات) |
| `ftpsrv-ps5.elf` | [ps5-payload-dev/ftpsrv](https://github.com/ps5-payload-dev/ftpsrv) v0.21.1 | سيرفر FTP على الجهاز |
| `websrv-ps5.elf` | [ps5-payload-dev/websrv](https://github.com/ps5-payload-dev/websrv) v0.34 | سيرفر ويب على 8080 (تصفح ملفات الجهاز) |
| `elfldr-ps5.elf` | [ps5-payload-dev/elfldr](https://github.com/ps5-payload-dev/elfldr) v0.26 | نفسه الـ loader، يرفع على 9020 |

الترتيب على 13.60: **kstuff** وبعدين **ShadowMountPlus**. etaHEN 2.5B موجه لـ 8.40–10.01
وربما ما يشتغل على 13.60.

الملفات كلها ELF64 x86-64 (حتى `etaHEN-2.5B.bin`)، وكل واحد `e_shoff + e_shnum*64` يساوي
حجمه بالضبط، يعني الـ `elfldr` يقرأه كامل.

## الترتيب

1. **JB 13.60** — تشتغل الاستغلال في متصفح الـ PS5 (User's Guide). انتظر حتى يطلع:
   `[+] elfldr is listening on port 9021`.
2. ارجع للصفحة (زر الرجوع في المتصفح) واضغط **Send to PS5**.

الاستغلال نفسه (`relapse`) يدعم 7.00 – 13.60، ومصدره:
<https://github.com/soniciso1/relapse> — صفحة `Payloads (sender)` عنده ترسل الـ payloads
من الجهاز مباشرة، فعنده بديل عن زر Send.

## طريقة عمل زر Send

الصفحة تطلب من `elfldr` على الجهاز نفسه:

```
GET http://127.0.0.1:9021/?uri=https%3A%2F%2F12lie20.github.io%2Fps5-elf-sender%2Fcrlr69.elf
```

الـ PS5 يسحب الملف من GitHub Pages ويشغّله. ما فيه أي PC في المعادلة.

الصفحة تحاول `fetch` أولاً، وإذا المتصفح منعها (mixed content: صفحة https تطلب http) تسوي
`window.location` — التنقل بين الصفحات ما يخضع لقاعدة mixed content، فدايماً يوصل الطلب.

## المتطلبات

- PS5 عليه jailbreak و`elfldr` شغّال على المنفذ 9021:
  ```
  wget -q -O - https://github.com/ps5-payload-dev/elfldr/releases/latest/download/elfldr-ps5.elf | nc -q0 <PS5_IP> 9020
  ```
- إنترنت على الـ PS5، عشان يسحب الـ ELF من GitHub.

## تبديل البايلود

ارفع الملف إلى نفس المستودع (مثلاً `foo.elf`)، وغيّر في `index.html`:

```js
var PAYLOAD_URL = 'https://12lie20.github.io/ps5-elf-sender/foo.elf';
```

وغيّر `<h1>` و`<title>` و`<p>` باسم الملف وحجمه.

## أدوات اختيارية من الـ PC

`bridge.py` / `bridge.js` يقبلان إرسال أي ملف من الكمبيوتر إلى PS5 على منفذ 9021
(بدون المتصفح)، ويقدّمان نفس الصفحة على `http://127.0.0.1:8765/` — نسخة `http` ما تتأثر
بقاعدة mixed content:

```
python bridge.py --send foo.elf --ps5-host 192.168.1.50
```

## البروتوكول على 9021

`elfldr` يقرأ أول 4 بايت:

| السحر | المعنى |
|---|---|
| `7f 45 4c 46` | ملف ELF خام |
| `47 45 54 20` (`GET `) | طلب HTTP — `GET /?uri=<url>` والـ PS5 يجيب الملف بنفسه |
| `70 74 74 68` | رابط `http(s)://` |
| `66 69 6c 65` | مسار على ذاكرة الـ PS5 |

## الملفات

```
index.html        الصفحة
crlr69.elf        البايلود (236880 بايت)
payloads/         الأدوات (kstuff, shadowmountplus, etaHEN, ftpsrv, websrv, elfldr)
bridge.py         إرسال من الكمبيوتر (اختياري)
bridge.js         نفس الشي بـ Node (اختياري)
```
