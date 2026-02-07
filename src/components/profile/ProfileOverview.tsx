import React, { FC } from 'react';

interface ProfileOverviewProps {
  user: { email?: string; name?: string } | undefined;
  onLogout: () => void;
}

const ProfileOverview: FC<ProfileOverviewProps> = ({ user, onLogout }) => {
  return (
    <div className="overview-content">
      <div className="profile-sidebar">
        <div className="user-avatar">
          <svg width="120" height="120" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M12 12q-1.65 0-2.825-1.175T8 8q0-1.65 1.175-2.825T12 4q1.65 0 2.825 1.175T16 8q0 1.65-1.175 2.825T12 12Zm-8 8v-2.8q0-.85.438-1.563T5.6 14.55q1.55-.775 3.15-1.163T12 13q1.65 0 3.25.388t3.15 1.162q.725.375 1.163 1.088T20 17.2V20H4Z"
            />
          </svg>
        </div>
        <button className="logout-button" onClick={onLogout}>
          Выйти
        </button>
      </div>

      <div className="profile-main-content">
        <div className="section">
          <h3>Основная информация</h3>
          <div className="info-grid">
            <div className="info-label">Email</div>
            <div className="info-value">{user?.email || 'example@gmail.com'}</div>
            <div className="info-label">Полное имя</div>
            <div className="info-value">{user?.name || 'Davud'}</div>
            <div className="info-label">Имя</div>
            <div className="info-value">Davud</div>
            <div className="info-label">Логин</div>
            <div className="info-value">davud</div>
          </div>
        </div>

        <div className="section">
          <h3>Последние действия</h3>
          <div className="activity-list">
            <div className="activity-item">
              <div className="activity-date">2024-02-15 14:30</div>
              <div className="activity-text">Загружена панорама "city_center_01"</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfileOverview;