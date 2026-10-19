# PS5 ELF Sender

صفحة ويب (جاهزة لـ GitHub Pages) فيها زر واحد يرسل ملف `.elf` إلى جهاز **PS5**
عبر منفذ **9021** — وهو منفذ خدمة `elfldr` من مشروع
[ps5-payload-dev/elfldr](https://github.com/ps5-payload-dev/elfldr) التي تستقبل
الـ payloads وتشغّلها على الجهاز.

```
┌────────────────────────┐   HTTP    ┌──────────────┐   TCP/9021   ┌─────────┐
│  الصفحة (github.io)    │ ────────▶ │  bridge.py   │ ───────────▶ │   PS5   │
│  زر: "إرسال إلى PS5"   │           │  (جهازك)     │   ملف ELF    │ (elfldr)│
└────────────────────────┘           └──────────────┘              └─────────┘
```

---

## 1. التشغيل السريع

1. **شغّل الجسر على جهازك** (نفس الجهاز الذي ستفتح منه الصفحة):

   ```powershell
   cd ps5-elf-sender
   python bridge.py
   ```
   أو بدون بايثون:
   ```powershell
   node bridge.js
   ```

2. **افتح الصفحة** (من GitHub Pages أو محلياً على <http://127.0.0.1:8765/>).

3. **اكتب IP الـ PS5** (مثال `192.168.1.50`) واضغط **"إرسال الـ ELF إلى PS5"**.

الصفحة ترسل `crlr69.elf` المرفق افتراضياً، ويمكنك أيضاً سحب أي ملف `.elf` آخر
onto الصفحة أو اختياره من جهازك.

> تأكد أن `elfldr` يعمل على الـ PS5 على المنفذ 9021. إن لم يكن كذلك:
> `wget -q -O - https://github.com/ps5-payload-dev/elfldr/releases/latest/download/elfldr-ps5.elf | nc -q0 <PS5_IP> 9020`

---

## 2. لماذا يوجد جسر؟

المتصفحات **لا تستطيع** فتح منفذ TCP خام، و `github.io` يعمل عبر `HTTPS` فقط.
لذلك:

| الوضع | كيف يعمل | متى يعمل |
|---|---|---|
| **عبر الجسر** (افتراضي) | الصفحة ترسل الملف إلى `bridge.py` عبر HTTP، والجسر يفتح اتصال TCP عادي إلى `PS5:9021` ويرسل الـ ELF خاماً | دائماً ✓ |
| **مباشر** | الصفحة ترسل `GET /?uri=…` إلى `PS5:9021` والـ PS5 يسحب الملف بنفسه | فقط إذا كانت الصفحة عبر `http://` (مثلاً `http://127.0.0.1:8765/` أو `http://192.168.x.x:8765/`). من `https://` المتصفح يمنعها (Mixed Content) |

الجسر يستمع على `127.0.0.1` فقط، ويرسل رؤوس CORS + `Access-Control-Allow-Private-Network`
حتى لا يمنعك المتصفح (Private Network Access) عند الاتصال من صفحة `https://`.

---

## 3. النشر على GitHub Pages

```bash
cd ps5-elf-sender
git init
git add .
git commit -m "PS5 ELF sender"
git branch -M main
git remote add origin https://github.com/<USER>/<REPO>.git
git push -u origin main
```

ثم:

* **عبر `gh`:**
  ```bash
  gh repo create <REPO> --public --source=. --push
  gh api -X POST repos/<USER>/<REPO>/pages -f source[branch]=main -f source[path]=/   # أو من الإعدادات
  ```
* **عبر واجهة GitHub:** `Settings → Pages → Build and deployment → Source: Deploy from a branch → main / (root)`.

بعد النشر الرابط يكون: `https://<USER>.github.io/<REPO>/`

ملاحظات:
* الملف `.nojekyll` موجود حتى يقدّم GitHub ملف `.elf` كما هو دون معالجة Jekyll.
* تأكد أن `crlr69.elf` مرفوع مع المستودع (236 KB) — هو الحمولة الافتراضية.

---

## 4. أوامر الجسر

```powershell
# خادم عادي على 127.0.0.1:8765
python bridge.py

# إتاحته لكل أجهزة الشبكة (حتى يفتحه PS5 نفسه أو جوالك)
python bridge.py --host 0.0.0.0

# إرسال ملف مباشرة من الطرفية (بدون صفحة)
python bridge.py --send crlr69.elf --ps5-host 192.168.1.50
python bridge.py --send crlr69.elf --ps5-host 192.168.1.50 --ps5-port 9021

# نفس الشيء بـ Node
node bridge.js --send crlr69.elf --ps5-host 192.168.1.50
```

### واجهة HTTP التي تستخدمها الصفحة

| الطريقة | المسار | الوصف |
|---|---|---|
| `GET` | `/info` | معلومات الجسر + عناوين IP المحلية |
| `GET` | `/ping?host=IP&port=9021` | اختبار اتصال TCP بالـ PS5 |
| `POST` | `/send?host=IP&port=9021` | body = ملف ELF كامل → يُرسل عبر TCP ويقرأ الرد |
| `GET` | `/<file>` | ملفات ثابتة (الصفحة والحمولة) |

---

## 5. البروتوكول على المنفذ 9021

`elfldr` يقرأ أول 4 بايت ليعرف نوع الحمولة:

| السحر (LE) | المعنى |
|---|---|
| `7f 45 4c 46` (`\x7fELF`) | ملف ELF — **وهو ما يرسله الجسر**: الملف كاملاً بالترتيب |
| `70 74 74 68` (`http`) | رابط `http://` أو `https://` يُجلبه الـ PS5 |
| `66 69 6c 65` (`file`) | مسار على ذاكرة الـ PS5 |
| `47 45 54 20` (`GET `) | طلب HTTP — مثاله: `GET /?uri=<encoded url>` |
| `4F 15 3D 1D` / `54 14 F5 EE` | SELF (PS4 / PS5) |

بالنسبة لملف ELF تحديداً، الخادم يقرأ:

1. 64 بايت (رأس `Elf64_Ehdr`).
2. `e_shoff + e_shnum * 64` بايت.
3. إن كانت هناك أقسام أبعد من ذلك، يكمل الباقي.

لملف `crlr69.elf` الحالي: `e_shoff = 235408` و `e_shnum = 23` ⇒
`235408 + 23*64 = 236880` بايت = **حجم الملف بالضبط**، أي أن إرسال الملف كاملاً
يكفي تماماً (لو نقصت بايتات يتوقف التحميل عند `recv`).

---

## 6. استكشاف الأخطاء

| العَرَض | السبب | الحل |
|---|---|---|
| `تعذّر الاتصال (هل الجسر يعمل؟)` | الجسر مغلق أو الرابط خطأ | شغّل `python bridge.py` وتأكد أن الرابط `http://127.0.0.1:8765` |
| المتصفح يمنع الطلب في الوضع المباشر | صفحة `https://` تطلب `http://` (Mixed Content) | استخدم وضع **الجسر**، أو افتح الصفحة من `http://127.0.0.1:8765/` |
| `لا يوجد رد من الجهاز` | طبيعي — الـ payload يشتغل بدون طباعة | الإرسال تم بنجاح إن ظهر `تم الإرسال` في السجل |
| `الجهاز أغلق الاتصال بدون رد` | الـ PS5 رفض الحمولة (مثال: ملف غير ELF) | تحقق أن الملف ELF 64-bit وأن `elfldr` يعمل |
| `TCP ... failed: timeout` | الـ PS5 غير موجود على هذا IP/المنفذ | تأكد من IP الـ PS5 وأنه على نفس الشبكة، وأن `elfldr` يعمل |
| الحاسوب/الراوتر يمنع الاتصال | جدار ناري | اسمح لـ Python/Node على المنفذ 8765، وتأكد أن الـ PS5 ليس معزولاً (Client Mode / AP) |
| `SHA-256 غير متاح` | الصفحة عبر `http://` غير localhost | `crypto.subtle` يحتاج https — لا يهم، هو للعرض فقط |

---

## 7. الملفات

```
ps5-elf-sender/
├── index.html     # الصفحة (HTML + CSS + JS مدمج، بدون build step)
├── crlr69.elf     # الحمولة الافتراضية (236880 بايت)
├── bridge.py      # الجسر - بايثون قياسية فقط
├── bridge.js      # الجسر - Node بدون مكتبات
├── .nojekyll      # يمنع Jekyll من لمس الملفات
└── README.md
```
