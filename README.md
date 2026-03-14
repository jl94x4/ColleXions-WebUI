<div align="center">
  <width="100%" alt="ColleXions Banner" />

  # 🎬 ColleXions
  **The Ultimate Plex Collection Manager & Automation Tool**

  [![GitHub Stars](https://img.shields.io/github/stars/jl94x4/ColleXions-WebUI?style=for-the-badge)](https://github.com/jl94x4/ColleXions-WebUI/stargazers)
  [![Docker Support](https://img.shields.io/badge/Docker-Supported-blue?style=for-the-badge&logo=docker)](https://github.com/jl94x4/ColleXions-WebUI)
  [![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
</div>

---

## 🌟 Overview

**ColleXions** is a powerful, modern web interface designed to give you total control over your Plex Library collections. It combines intelligent automation with a beautiful management dashboard to ensure your Plex Home screen is always fresh, relevant, and stunning.

Whether you want to rotate trending movies, automatically pin seasonal collections, or sync discovery lists from TMDB, Trakt, and MdbList—ColleXions handles it all.

---

## ✨ Key Features

- 🎡 **Automated Home Pinning**: Automatically rotate which collections are pinned to your Plex Home screen based on intervals you define.
- 🔄 **Multi-Source Auto-Sync**: Sync your Plex collections directly with dynamic lists from:
  - **TMDb** (Trending, Top Rated, Genre-based)
  - **Trakt.tv** (Trending, Anticipated, Personal Lists)
  - **MdbList** (Custom community lists)
- 📅 **Seasonal Specials**: Set-and-forget seasonal pinning (e.g., automatically pin "Halloween Horror" every October).
- 🛠️ **Visual Collection Builder**: A robust UI to search, filter, and create new collections across all your libraries.
- 📊 **Insightful Dashboard**: track pinning history, view unique item stats, and monitor background sync jobs.
- 🛡️ **Admin Security**: JWT-based authentication to keep your settings and Plex tokens secure.
- 🐳 **Docker Ready**: Deploy in seconds using Docker Compose.

---

## 🚀 Getting Started

### 🐳 Option 1: Docker (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jl94x4/ColleXions-WebUI.git
   cd ColleXions-WebUI
   ```

2. **Prepare your config:**
   ```bash
   cp config/config.example.json config/config.json
   ```

3. **Launch with Docker Compose:**
   ```bash
   docker compose up -d
   ```
   *The app will be available at `http://localhost:5000` (or your mapped port).*

---

## ⚙️ Configuration

ColleXions uses a `config.json` file located in the `config/` directory.

> [!TIP]
> Use the **Onboarding** flow in the Web UI to set up your Plex URL, Token, and API keys visually! 

### **Supported API Integrations**
- **Plex**: Required for all core functionality.
- **TMDb**: For trending collections and poster lookups.
- **Trakt.tv**: For anticipated and trending syncs.
- **MdbList**: For advanced community list syncing.
- **Discord**: Optional webhooks for pinning notifications.

---

## 🛠️ Tech Stack

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons.
- **Backend**: Python (Flask), PlexAPI, JWT for Auth.
- **Deployment**: Docker, Docker Compose.

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests to help improve ColleXions.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  Developed by <b>jl94x4</b>
</div>
