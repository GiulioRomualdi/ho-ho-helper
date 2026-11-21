<div align="center">

# 🎅 Ho-Ho-Helper 🎁

**A fair, friendly and fuss-free Secret Santa organizer.**

[![CI](https://github.com/GiulioRomualdi/ho-ho-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/GiulioRomualdi/ho-ho-helper/actions/workflows/ci.yml)
[![Pixi Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

List your friends, add a few rules, and let the elves 🧝 draw the names
and email everyone their secret match.

</div>

---

## ✨ Features

| | |
|---|---|
| 🎲 **Truly fair draw** | Every valid arrangement has exactly the same chance of being picked, and the randomness comes from your operating system's entropy source. |
| 💑 **Constraints** | Keep couples from drawing each other, or block any one-way pair (*"Alice can't gift Charlie"*). |
| 📅 **No repeats from last year** | Pass last year's results and nobody gets the same person again. |
| 🔁 **Single gift loop** | Optionally make the gifts go around one big loop through everyone: A → B → C → … → A. |
| 📬 **Email delivery** | Sends every participant their match, so even the organizer can take part without peeking. |
| 💸 **Budget reminder** | Puts the maximum budget and currency in the emails. |
| 🛡️ **Safe by default** | Catches typos in names, never overwrites a previous draw, and stops with a clear error if no draw is possible. |

---

## 🚀 Quick start

Ho-Ho-Helper uses [**pixi**](https://pixi.sh) to manage its environment.

1. **Install pixi** (once):
   ```bash
   curl -fsSL https://pixi.sh/install.sh | sh        # Linux / macOS
   # or: powershell -ExecutionPolicy ByPass -c "irm -useb https://pixi.sh/install.ps1 | iex"   (Windows)
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/GiulioRomualdi/ho-ho-helper.git
   cd ho-ho-helper
   ```

3. **Draw the names** 🎉:
   ```bash
   pixi run start
   ```
   pixi installs everything on the first run. Use `pixi run start --help` to see all the options.

> [!TIP]
> Prefer plain `pip`? `pip install .` installs the `ho-ho-helper` command as well (Python ≥ 3.11).

---

## 🎄 Usage

### 1. Describe your group

Edit [`participants.toml`](participants.toml), or create your own file and pass it with `-f`:

```toml
[participants]
names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]

# Optional: needed only to deliver the assignments via email (-e)
[participants.emails]
Alice = "alice@example.com"
Bob = "bob@example.com"
Charlie = "charlie@example.com"
Diana = "diana@example.com"
Eve = "eve@example.com"

# Optional: added to the emails
[gift]
max_budget = 10
currency = "EUR"

# Optional
[constraints]
couples = [["Alice", "Bob"], ["Diana", "Eve"]]  # they never draw each other
direct_constraints = [["Alice", "Charlie"]]     # Alice can't draw Charlie (Charlie can still draw Alice)
```

Names in `emails` and `constraints` must match `names` exactly. A typo gives an error instead of being silently ignored.

### 2. Run the draw

```bash
pixi run start -o assignments-2026.toml
```

### 3. Next year, avoid repeating matches 📅

```bash
pixi run start -o assignments-2027.toml -p assignments-2026.toml
```

`-p/--previous` can be passed several times to skip matches from more than one past year.

> [!NOTE]
> **"Why did I get the same person as last year?"** Even with a perfectly fair draw, two independent
> years share **at least one pair about 2 times out of 3**, whatever the size of the group
> (≈ 83% for the example above). That is chance, not a broken random generator. Use `--previous`
> to rule it out.

### ⚙️ All options

| Option | Description |
|---|---|
| `-f, --file FILE` | Participants file (default: `participants.toml`) |
| `-o, --output FILE` | Where to save the assignments (default: `assignments.toml`); an existing file is never overwritten unless you pass `--force` |
| `-p, --previous FILE` | Results of a past edition; its pairs are excluded (repeatable) |
| `--single-cycle` | All gifts form a single loop through every participant |
| `-e, --email` | Email each participant their match |
| `--smtp-server`, `--smtp-port` | SMTP server (default: `smtp.gmail.com:587`, STARTTLS) |
| `--seed N` | Reproducible draw, for testing only |
| `--force` | Overwrite the output file |
| `-y, --yes` | Don't ask for confirmation |

---

## 📬 Email delivery

With `-e`, you're asked for your email address and password after the draw. To use Gmail:

1. Turn on **2-Step Verification** for your Google account.
2. Create an **App Password** ([Google's instructions](https://support.google.com/mail/answer/185833)).
3. Enter your Gmail address and the App Password when asked.

For other providers, use `--smtp-server` and `--smtp-port`.

Every participant gets an email like this:

```
🎅 Ho Ho Ho, Alice! 🎁

You have been chosen as the Secret Santa for... 🥁 *Diana*! 🎉

✨ Make sure to prepare a thoughtful gift 🎁 and spread the holiday cheer! 🎄
💸 Remember: the maximum budget is 10 EUR.

Wishing you a season full of joy, laughter, and surprises! ❄️

Happy Holidays! 🕊️

    Your Secret Santa Organizer 🎅
```

The assignments are also saved to the output file:

```toml
[assignments]
Alice = "Diana"
Bob = "Charlie"
Charlie = "Eve"
Diana = "Bob"
Eve = "Alice"
```

> [!WARNING]
> The output file reveals every match. Don't open it if you're playing too! Files named
> `assignments*.toml` are git-ignored, so they can't be committed by accident.

---

## 🎲 How the draw works

Ho-Ho-Helper uses *rejection sampling*. It shuffles the participants uniformly at random,
and keeps the result only if it respects every rule (nobody gifts themselves, no blocked pairs, and a
single loop when `--single-cycle` is on). Otherwise it shuffles again. Every valid arrangement is
therefore **exactly equally likely**. For `--single-cycle`, a random order of the participants is
turned into a loop, where each person gifts the next one.

If the rules are so strict that valid arrangements are extremely rare, it lists all of them and
picks one at random. If there are none, it says so clearly.

The test suite checks all of this. It lists every valid arrangement by brute force and runs a
chi-square test to confirm that the draws are uniform.

---

## 🛠️ Development

```bash
pixi run test     # run the test suite
pixi run lint     # ruff lint + format check
pixi run format   # auto-format the code
```

Contributions are welcome! Fork the repository, create a branch, and open a pull request. 🎁

## 📄 License

Released under the [MIT License](LICENSE).
