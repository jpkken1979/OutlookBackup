---
name: telegram-bot-builder
description: >-
type: feature
---
  Use when building or optimizing Telegram bots. Triggers: telegram bot, bot
  api, telegraf, aiogram, inline keyboard, webhook, bot monetization, user
  onboarding.
type: feature
metadata:
  category: automation
  author: ozy
  triggers: telegram, bot, telegraf, aiogram, chat, notifications
  references: Rules.md, AGENTS.md

# Telegram Bot Mastery (God Mode) 🤖

Expert principles for building natural, responsive, and high-retention Telegram bots.

## 💎 Core Principles (Axioms)
1. **Be an Assistant, Not a Script**: Bots should feel natural. Use typing indicators and clear, concise language.
2. **Never Block the User**: Long-running operations must be handled asynchronously. Acknowledge the command immediately, then send the result when ready.
3. **UX Over Complexity**: Use Inline Keyboards and Menu Buttons instead of forcing users to type commands.
4. **Safety First**: Never trust user input. Sanitize all messages and handle edge cases (empty strings, large files, unsupported types).
5. **State Awareness**: Maintain user context using a persistent store (Redis/DB) to handle multi-step interactions (Wizards/Menus).

## 🛠️ Step-by-Step implementation
1. **The Handshake Phase**: Register with @BotFather and set up basic commands (/start, /help, /settings).
2. **The Interface Phase**: Design the conversation flow using Inline Keyboards and Reply Markups.
3. **The Logic Phase**: Implement the handlers using Telegraf (JS) or Aiogram (Python). Use middleware for auth/logging.
4. **The Deployment Phase**: Configure webhooks for production stability and set up monitoring/alerts.

## 🛡️ Security & Quality Checklist
- [ ] **Rate Limiting**: Are we protecting the bot from flood attacks?
- [ ] **Blocking Check**: Are there any long `await` calls that freeze the bot for other users?
- [ ] **Error Handler**: Is there a global `catch` to prevent the bot from crashing on unhandled errors?
- [ ] **Privacy Mode**: Is the bot configured with the correct privacy settings in @BotFather?
- [ ] **Feedback Loop**: Does the bot notify the user if an action is taking longer than expected?

## 📚 Examples (Few-shot)

### Example: Async Command Handler (JS/Telegraf)
```javascript
// ✅ God Mode: Immediate feedback, async processing
bot.command('generate', async (ctx) => {
  await ctx.sendChatAction('typing'); // Visual feedback
  await ctx.reply('⏳ Generating your report, please wait...');
  
  // Hand off to background worker or async service
  generateReport(ctx.from.id).then(file => {
    ctx.replyWithDocument({ source: file });
  });
});
```

### Example: Dynamic Inline Keyboard
```javascript
// ✅ God Mode: Intuitive menu
const menu = Markup.inlineKeyboard([
  [Markup.button.callback('Settings ⚙️', 'open_settings')],
  [Markup.button.callback('Get Help ❓', 'show_help')]
]);
```

---
*Skill: telegram-bot-builder v2.0 (Bibek Poudel Edition)*
