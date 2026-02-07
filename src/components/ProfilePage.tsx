import React, { FC, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from './Header'; // Проверьте путь импорта
import { useAuth } from '../hooks/useAuth';

// Импорт под-компонентов
import ProfileOverview from './profile/ProfileOverview';
import ProfileVector from './profile/ProfileVector';
import ProfilePanoramas from './profile/ProfilePanoramas';
import ProfileOrthophotos from './profile/ProfileOrthophotos';
import ProfileDashboard from './profile/ProfileDashboard';

type TabType = 'overview' | 'vector' | 'panoramas' | 'ortho' | 'dashboard';

const ProfilePage: FC = () => {
  const navigate = useNavigate();
  const { logout, user } = useAuth() as any; // Типизацию useAuth лучше взять из хука
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="background">
      <Header />
      <div className="profile-page">
        <div className="navigation-tabs">
          <button className={`tab-button ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
            Обзор
          </button>
          <button className={`tab-button ${activeTab === 'vector' ? 'active' : ''}`} onClick={() => setActiveTab('vector')}>
            Вектор
          </button>
          <button className={`tab-button ${activeTab === 'panoramas' ? 'active' : ''}`} onClick={() => setActiveTab('panoramas')}>
            Панорамы
          </button>
          <button className={`tab-button ${activeTab === 'ortho' ? 'active' : ''}`} onClick={() => setActiveTab('ortho')}>
            Ортофотопланы
          </button>
          <button className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
            Дашборд
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'overview' && <ProfileOverview user={user} onLogout={handleLogout} />}
          {activeTab === 'vector' && <ProfileVector />}
          {activeTab === 'panoramas' && <ProfilePanoramas />}
          {activeTab === 'ortho' && <ProfileOrthophotos />}
          {activeTab === 'dashboard' && <ProfileDashboard />}
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;