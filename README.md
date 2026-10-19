# PS5 ELF Sender

صفحة تفتحها **على جهاز PS5 نفسه**، تضغط زر، والـ payload يشتغل.

**https://12lie20.github.io/ps5-elf-sender/**

## طريقة العمل

1. الصفحة تحمّل `crlr69.elf` من GitHub Pages.
2. لما تضغط **Send to PS5**، الصفحة تطلب من `elfldr` على الجهاز نفسه:

   ```
   GET http://127.0.0.1:9021/?uri=https%3A%2F%2F12lie20.github.io%2Fps5-elf-sender%2Fcrlr69.elf
   ```

3. الـ PS5 يسحب الملف من GitHub ويشغّله. ما فيه أي PC في المعادلة.

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
index.html    الصفحة
crlr69.elf    البايلود (236880 بايت)
bridge.py     إرسال من الكمبيوتر (اختياري)
bridge.js     نفس الشي بـ Node (اختياري)
```
