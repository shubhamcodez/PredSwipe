# PredSwipe 🎯

A Tinder-like React app for swiping on predictions across different market categories.

## Features

- 🔐 **User Login**: Simple username and email authentication
- 🎯 **Category Selection**: Choose from Football, Basketball, Tennis, Crypto, Stocks, or Random
- 👆 **Swipe Interface**: Swipe right for "Yes" or left for "No" on predictions
- ⌨️ **Keyboard Controls**: Use arrow keys (← for No, → for Yes)
- 📊 **Statistics**: Track your Yes/No votes and progress
- 📱 **Responsive Design**: Works on desktop and mobile devices

## Getting Started

### Prerequisites

- Node.js (version 14 or higher)
- npm or yarn

### Installation

1. Clone the repository or navigate to the project directory
2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

4. Open [http://localhost:3000](http://localhost:3000) to view it in the browser

## How to Use

1. **Login**: Enter your username and email to get started
2. **Choose Category**: Select your preferred market category or choose "Random" for a mix
3. **Start Swiping**: 
   - Swipe right or press → arrow key for "Yes"
   - Swipe left or press ← arrow key for "No"
   - Track your progress and statistics
4. **Complete Session**: When you finish all predictions, view your stats and start a new session

## Categories & Predictions

- **Football**: Premier League, Champions League predictions
- **Basketball**: NBA, EuroLeague predictions  
- **Tennis**: Grand Slams, ATP/WTA predictions
- **Crypto**: Bitcoin, Ethereum, altcoin predictions
- **Stocks**: Tech, finance, market trend predictions
- **Random**: Mix of all categories

## Technologies Used

- React 18
- React Router DOM
- CSS3 with modern features
- Responsive design principles
- Keyboard event handling

## Project Structure

```
src/
├── components/
│   ├── Login.js
│   ├── Login.css
│   ├── CategorySelection.js
│   ├── CategorySelection.css
│   ├── SwipeInterface.js
│   └── SwipeInterface.css
├── App.js
├── App.css
├── index.js
└── index.css
```

## Customization

You can easily customize the app by:

- Adding new categories in `CategorySelection.js`
- Adding new predictions in `SwipeInterface.js`
- Modifying the styling in the CSS files
- Adding new features like user profiles or prediction history

## Future Enhancements

- User authentication with backend
- Prediction history and analytics
- Social features (sharing, leaderboards)
- Real-time prediction updates
- More categories and prediction types

Enjoy swiping through predictions! 🎯
