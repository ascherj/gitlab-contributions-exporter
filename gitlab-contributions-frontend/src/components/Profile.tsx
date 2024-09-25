import { useEffect, useState } from 'react';
import styled from 'styled-components';

interface User {
  id: number;
  name: string;
  username: string;
  email: string;
}

interface GitlabContribution {
  contribution_type: string;
  message: string;
  project_id: number;
  date: string;
  instance: string;
}

const ProfileContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
`;

const ContributionsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
  margin-top: 20px;
`;

const ContributionCard = styled.div`
  background-color: #f5f5f5;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;

const ContributionTitle = styled.h3`
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 18px;
`;

const ContributionDetail = styled.p`
  margin: 5px 0;
  font-size: 14px;
`;

const Profile = () => {
  const [profile, setProfile] = useState<User | null>(null);
  const [contributions, setContributions] = useState<GitlabContribution[] | null>(null);
  const getProfile = async () => {
    const response = await fetch('http://localhost:8000/profile', {
      credentials: 'include',
    });
    return response;
  };

  const getContributions = async () => {
    const response = await fetch('http://localhost:8000/contributions', {
      credentials: 'include',
    });
    return response;
  };

  useEffect(() => {
    const fetchProfileAndContributions = async () => {
      try {
        const profileResponse = await getProfile();
        if (!profileResponse.ok) {
          throw new Error('Failed to fetch profile');
        }
        const profileData = await profileResponse.json();
        setProfile(profileData);

        const contributionsResponse = await getContributions();
        if (!contributionsResponse.ok) {
          throw new Error('Failed to fetch contributions');
        }
        const contributionsData = await contributionsResponse.json();
        console.log(contributionsData);
        setContributions(contributionsData);
      } catch (error) {
        console.error('Error fetching data:', error);
      }
    };

    fetchProfileAndContributions();
  }, []);

  if (!profile) {
    return <div>Loading...</div>;
  }

  return (
    <ProfileContainer>
      <h1>Welcome, {profile.name}</h1>
      <p>Username: {profile.username}</p>
      <p>Email: {profile.email}</p>
      <h2>Contributions</h2>
      <ContributionsGrid>
        {contributions && contributions.map((contribution, index) => (
          <ContributionCard key={index}>
            <ContributionTitle>{contribution.contribution_type}</ContributionTitle>
            <ContributionDetail><strong>Message:</strong> {contribution.message}</ContributionDetail>
            <ContributionDetail><strong>Project ID:</strong> {contribution.project_id}</ContributionDetail>
            <ContributionDetail><strong>Date:</strong> {new Date(contribution.date).toLocaleDateString()}</ContributionDetail>
            <ContributionDetail><strong>Instance:</strong> {contribution.instance}</ContributionDetail>
          </ContributionCard>
        ))}
      </ContributionsGrid>
    </ProfileContainer>
  );
};

export default Profile;
