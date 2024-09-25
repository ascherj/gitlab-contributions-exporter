import React, { useEffect, useState } from 'react';

interface User {
  id: number;
  name: string;
  username: string;
  email: string;
}

const Profile = () => {
  const [profile, setProfile] = useState<User | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/profile', {
      credentials: 'include',  // Include cookies in the request
    })
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch profile');
        }
        return response.json();
      })
      .then(data => setProfile(data))
      .catch(error => {
        console.error('Error fetching profile:', error);
      });
  }, []);

  if (!profile) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>Welcome, {profile.name}</h1>
      <p>Username: {profile.username}</p>
      <p>Email: {profile.email}</p>
    </div>
  );
};

export default Profile;
