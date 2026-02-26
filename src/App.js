import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import Login from './components/Login';
import CategorySelection from './components/CategorySelection';
import SwipeInterface from './components/SwipeInterface';
import './App.css';

function AppContent() {
  const [user, setUser] = useState({ 
    username: '', 
    email: '',
    kalshiApiKey: '',
    kalshiPrivateKey: ''
  });
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Check sessionStorage on mount to restore session
    const savedApiKey = sessionStorage.getItem('kalshiApiKey');
    const savedPrivateKey = sessionStorage.getItem('kalshiPrivateKey');
    
    if (savedApiKey && savedPrivateKey) {
      setUser({
        username: 'User',
        email: 'user@predswipe.com',
        kalshiApiKey: savedApiKey,
        kalshiPrivateKey: savedPrivateKey
      });
      setIsLoggedIn(true);
    }
  }, []);

  const handleLogin = (userData) => {
    setUser(userData);
    setIsLoggedIn(true);
    navigate('/categories');
  };

  const handleCategorySelect = (category) => {
    setSelectedCategory(category);
    navigate('/swipe');
  };

  return (
    <Routes>
      <Route 
        path="/login" 
        element={<Login onLogin={handleLogin} />}
      />
      <Route 
        path="/categories" 
        element={
          !isLoggedIn ? <Navigate to="/login" replace /> :
          <CategorySelection 
            onCategorySelect={handleCategorySelect}
            onBack={() => setSelectedCategory(null)}
            user={user}
          />
        } 
      />
      <Route 
        path="/swipe" 
        element={
          !isLoggedIn ? <Navigate to="/login" replace /> :
          !selectedCategory ? <Navigate to="/categories" replace /> :
          <SwipeInterface 
            category={selectedCategory}
            user={user}
            onBack={() => {
              setSelectedCategory(null);
              navigate('/categories');
            }}
          />
        } 
      />
      <Route path="/" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <Router>
      <div className="App">
        <AppContent />
      </div>
    </Router>
  );
}

export default App;
