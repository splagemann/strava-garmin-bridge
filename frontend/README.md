# Strava-Garmin Bridge Frontend

Modern React-based frontend for the Strava-Garmin Bridge application. Built with TypeScript, React Query, and Tailwind CSS for a fast and intuitive user experience.

## Tech Stack

- **React 18** with TypeScript
- **Vite** - Fast build tool and dev server
- **React Router v6** - Client-side routing
- **TanStack Query (React Query)** - Async state management
- **Axios** - HTTP client
- **Tailwind CSS** - Utility-first styling
- **Sonner** - Toast notifications

## Features

### Authentication
- Strava OAuth integration
- Garmin credentials management
- Automatic session handling

### Dashboard
- Real-time sync statistics
- Recent sync activity list
- Manual activity sync
- Success rate metrics

### Filters Management
- Create include/exclude filters
- Regular expression support
- Toggle filters on/off
- Pattern-based activity filtering

### Sync History
- Complete sync log with pagination
- Status filtering (success/failed/skipped)
- Retry failed syncs
- Detailed error messages

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running on http://localhost:8000

### Installation

```bash
# Install dependencies
npm install

# Create environment file
cp .env.example .env.local

# Update VITE_API_URL if needed
# Default: http://localhost:8000
```

### Development

```bash
# Start dev server
npm run dev

# Open browser to http://localhost:5173
```

### Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Environment Variables

Create a `.env.local` file:

```env
VITE_API_URL=http://localhost:8000
```

## Usage Flow

### First Time Setup

1. Visit `/auth` page
2. Click "Connect with Strava" → redirects to Strava OAuth
3. After redirect back, enter Garmin credentials
4. Both services connected → redirects to Dashboard

### Daily Usage

1. **Dashboard** - View sync stats and recent activity
2. **Manual Sync** - Enter Strava activity ID to sync immediately
3. **Filters** - Create rules to include/exclude activities
4. **History** - Review all syncs, retry failed ones

---

Built with ❤️ using React + TypeScript + Vite
