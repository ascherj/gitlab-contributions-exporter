import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const Welcome = () => {
  const [username, setUsername] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchUserData = async () => {
      const token = localStorage.getItem('token');
      if (!token) {
        navigate('/');
        return;
      }

      const response = await fetch('http://localhost:8000/users/me', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setUsername(data.username);
      } else {
        localStorage.removeItem('token');
        navigate('/');
      }
    };

    fetchUserData();
  }, [navigate]);

  return (
    <div>
      <h1>Welcome, {username}!</h1>
      <p>We're glad to have you here. Explore your GitLab contributions and more.</p>
    </div>
  );
};

export default Welcome;
