# Ho-Ho-Helper 🎅🎁

Bring holiday cheer to your Secret Santa event with **Ho-Ho-Helper**! This Python application makes organizing Secret Santa easy, fun, and hassle-free. 🎄✨ 

## ✨ Features
- 🤝 **Smart Assignments**: Ensures each participant is assigned a Secret Santa.
- 🔒 **Constraint Support**: Avoids conflicts like couples gifting each other or other custom constraints.
- 📝 **TOML-based Configuration**: Input participants and constraints via a user-friendly TOML file.
- 📤 **Optional Email Notifications**: Automatically send assignments to participants (optional).

---

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/GiulioRomualdi/ho-ho-helper.git
   cd ho-ho-helper
   ```

2. **Set up the environment**:
   Use the provided `environment.yml` file to create a Conda environment:
   ```bash
   conda env create -f environment.yml
   conda activate ho-ho-helper-env
   ```

---

## 🎄 Usage

1. **Prepare your participants**:
   Edit the `participants.toml` file to include:
   - A list of participant names.
   - Optional email addresses for sending notifications.
   - Constraints for assignments.

   Example `participants.toml`:
   ```toml
   [participants]
   names = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
   emails = {
       Alice = "alice@example.com",
       Bob = "bob@example.com",
       Charlie = "charlie@example.com",
       Diana = "diana@example.com",
       Eve = "eve@example.com"
   }

   [constraints]
   couples = [
       ["Alice", "Bob"],
       ["Diana", "Eve"]
   ]
   direct_constraints = [["Alice", "Charlie"]]
   ```

2. **Run the application**:
   Generate assignments:
   ```bash
   python -m ho_ho_helper.main
   ```

3. **Send email notifications** (optional):
   If emails are provided in `participants.toml`, you’ll be prompted to send notifications. Just provide your Gmail address and App Password (see below).

---

## 📬 Email Configuration

To send emails via Gmail:
1. Enable **2-Step Verification** for your Gmail account.
2. Generate an **App Password** (see [Google’s instructions](https://support.google.com/mail/answer/185833)).
3. Enter your Gmail credentials when prompted.

---

## 🎁 Example Output

When you run the application:
- Assignments are saved to `assignments.toml`:
  ```toml
  [assignments]
  Alice = "Charlie"
  Bob = "Diana"
  Charlie = "Eve"
  Diana = "Alice"
  Eve = "Bob"
  ```

- Email notifications (if enabled) look like this:
  ```
  🎅 Ho Ho Ho, Alice! 🎁
  
  You have been chosen as the Secret Santa for... 🥁 *Charlie*! 🎉

  ✨ Make sure to prepare a thoughtful gift 🎁 and spread the holiday cheer! 🎄

  Wishing you a season full of joy, laughter, and surprises! ❄️

  Happy Holidays! 🕊️
  - Your Secret Santa Organizer 🎅
  ```

---

## 🛠️ Contributing

Contributions are welcome! If you’d like to contribute:
1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/new-feature
   ```
3. Submit a pull request.

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

