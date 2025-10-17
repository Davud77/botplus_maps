// src/pages/ProfilePage.tsx
import React, { FC, useEffect, useState, KeyboardEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import Header from "./Header";
import { useAuth } from "../hooks/useAuth";
import { fetchPanoramas, fetchOrthophotos } from "../utils/api";

interface PanoItem {
  id: number | string;
  filename: string;
  latitude?: number;
  longitude?: number;
  tags?: string;
  upload_date?: string;
  [k: string]: any;
}

interface OrthoItem {
  id: number | string;
  filename: string;
  url: string;
  bounds: {
    north: number;
    south: number;
    east: number;
    west: number;
  };
  [k: string]: any;
}

interface AuthContextType {
  logout: () => void;
  user?: {
    email?: string;
    name?: string;
  };
}

const jsonHeaders = { "Content-Type": "application/json" as const };

const ProfilePage: FC = () => {
  const navigate = useNavigate();
  const { logout, user } = useAuth() as AuthContextType;

  const [activeTab, setActiveTab] = useState<"overview" | "panoramas" | "ortho" | "dashboard">("overview");

  // --- Панорамы ---
  const [panos, setPanos] = useState<PanoItem[]>([]);
  const [loadingPanos, setLoadingPanos] = useState(false);
  const [errorPanos, setErrorPanos] = useState("");

  const [editId, setEditId] = useState<number | string | null>(null);
  const [editTags, setEditTags] = useState<string>("");

  // --- Ортофотопланы ---
  const [orthos, setOrthos] = useState<OrthoItem[]>([]);
  const [loadingOrthos, setLoadingOrthos] = useState(false);
  const [errorOrthos, setErrorOrthos] = useState("");

  // -------------------------------------------------------------------------
  //                               ЗАГРУЗКА ДАННЫХ
  // -------------------------------------------------------------------------

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoadingPanos(true);
      setErrorPanos("");
      try {
        const data = await fetchPanoramas<any>();
        const list: PanoItem[] = Array.isArray(data) ? data : data?.data ?? data?.items ?? [];
        if (alive) setPanos(list);
      } catch (error: any) {
        if (!alive) return;
        const msg =
          error?.detail?.message ||
          (typeof error?.detail === "string" ? error.detail : undefined) ||
          error?.message ||
          "Ошибка при загрузке панорам";
        setErrorPanos(msg);
      } finally {
        if (alive) setLoadingPanos(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoadingOrthos(true);
      setErrorOrthos("");
      try {
        const data = await fetchOrthophotos<any>();
        const list: OrthoItem[] = Array.isArray(data) ? data : data?.data ?? data?.items ?? [];
        if (alive) setOrthos(list);
      } catch (error: any) {
        if (!alive) return;
        const msg =
          error?.detail?.message ||
          (typeof error?.detail === "string" ? error.detail : undefined) ||
          error?.message ||
          "Ошибка при загрузке ортофотопланов";
        setErrorOrthos(msg);
      } finally {
        if (alive) setLoadingOrthos(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // -------------------------------------------------------------------------
  //                           ОБРАБОТЧИКИ ДЕЙСТВИЙ
  // -------------------------------------------------------------------------

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleEdit = (panoId: number | string, currentTags: string = "") => {
    setEditId(panoId);
    setEditTags(currentTags);
  };

  const handleSaveTags = async (panoId: number | string) => {
    try {
      const res = await fetch(`/api/panoramas/${encodeURIComponent(String(panoId))}`, {
        method: "PUT",
        headers: jsonHeaders,
        credentials: "include",
        body: JSON.stringify({ tags: editTags }),
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(result?.error || result?.message || "Ошибка обновления");
      }
      setPanos((prev) => prev.map((p) => (p.id === panoId ? { ...p, tags: editTags } : p)));
      alert("Теги сохранены!");
      setEditId(null);
      setEditTags("");
    } catch (error: any) {
      alert(`Ошибка обновления: ${error?.message || "Неизвестная ошибка"}`);
    }
  };

  const handleEditKey = (e: KeyboardEvent<HTMLInputElement>, panoId: number | string) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void handleSaveTags(panoId);
    }
    if (e.key === "Escape") {
      setEditId(null);
      setEditTags("");
    }
  };

  const handleDelete = async (panoId: number | string) => {
    const confirmDel = window.confirm("Уверены, что хотите удалить панораму?");
    if (!confirmDel) return;

    try {
      const res = await fetch(`/api/panoramas/${encodeURIComponent(String(panoId))}`, {
        method: "DELETE",
        credentials: "include",
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(result?.error || result?.message || "Ошибка удаления");
      }
      setPanos((prev) => prev.filter((p) => p.id !== panoId));
      alert("Панорама удалена!");
    } catch (error: any) {
      alert(`Ошибка удаления: ${error?.message || "Неизвестная ошибка"}`);
    }
  };

  const handleDeleteOrtho = async (orthoId: number | string) => {
    const confirmDel = window.confirm("Удалить ортофотоплан?");
    if (!confirmDel) return;

    try {
      const res = await fetch(`/api/orthophotos/${encodeURIComponent(String(orthoId))}`, {
        method: "DELETE",
        credentials: "include",
      });
      const result = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(result?.error || result?.message || "Ошибка удаления ортофотоплана");
      }
      setOrthos((prev) => prev.filter((o) => o.id !== orthoId));
      alert("Ортофотоплан удалён!");
    } catch (error: any) {
      alert(`Ошибка удаления: ${error?.message || "Неизвестная ошибка"}`);
    }
  };

  // -------------------------------------------------------------------------
  //                           РЕНДЕР КОНТЕНТА ТАБОв
  // -------------------------------------------------------------------------

  const renderOverview = () => (
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
        <button className="logout-button" onClick={handleLogout}>
          Выйти
        </button>
      </div>

      <div className="profile-main-content">
        <div className="section">
          <h3>Основная информация</h3>
          <div className="info-grid">
            <div className="info-label">Email</div>
            <div className="info-value">{user?.email || "example@gmail.com"}</div>

            <div className="info-label">Полное имя</div>
            <div className="info-value">{user?.name || "Davud"}</div>

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
            <div className="activity-item">
              <div className="activity-date">2024-02-14 09:15</div>
              <div className="activity-text">Обновлены теги для панорамы #1245</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderPanoramas = () => (
    <div className="table-container">
      <div className="table-header">
        <h3>Мои панорамы</h3>
        <Link to="/upload">
          <button className="primary-button">+ Загрузить панораму</button>
        </Link>
      </div>

      {loadingPanos && <div>Загрузка панорам...</div>}
      {errorPanos && <div style={{ color: "red" }}>{errorPanos}</div>}

      {!loadingPanos && !errorPanos && panos.length === 0 && (
        <div className="empty-state">Нет загруженных панорам</div>
      )}

      {!loadingPanos && !errorPanos && panos.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Файл</th>
              <th>Теги</th>
              <th>Координаты</th>
              <th>Дата загрузки</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {panos.map((pano) => (
              <tr key={String(pano.id)} className={editId === pano.id ? "row-editing" : undefined}>
                <td>{pano.id}</td>
                <td>{pano.filename}</td>
                <td>
                  {editId === pano.id ? (
                    <input
                      type="text"
                      value={editTags}
                      onChange={(e) => setEditTags(e.target.value)}
                      onKeyDown={(e) => handleEditKey(e, pano.id)}
                      className="tags-input"
                      autoFocus
                    />
                  ) : (
                    pano.tags || "Нет тегов"
                  )}
                </td>
                <td>
                  {pano.latitude != null && pano.longitude != null
                    ? `${Number(pano.latitude).toFixed(5)}, ${Number(pano.longitude).toFixed(5)}`
                    : "N/A"}
                </td>
                <td>{pano.upload_date ? new Date(pano.upload_date).toLocaleDateString() : "—"}</td>
                <td>
                  <div className="actions-group">
                    {editId === pano.id ? (
                      <>
                        <button
                          className="success-button"
                          onClick={() => handleSaveTags(pano.id)}
                          disabled={editTags === (pano.tags || "")}
                        >
                          &#10003;
                        </button>
                        <button
                          className="icon-button"
                          onClick={() => {
                            setEditId(null);
                            setEditTags("");
                          }}
                          title="Отмена"
                        >
                          ✕
                        </button>
                      </>
                    ) : (
                      <button className="icon-button" onClick={() => handleEdit(pano.id, pano.tags || "")} title="Редактировать теги">
                        ✎
                      </button>
                    )}

                    <button className="danger-button" onClick={() => handleDelete(pano.id)} title="Удалить">
                      &times;
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  const renderOrtho = () => (
    <div className="table-container">
      <div className="table-header">
        <h3>Ортофотопланы</h3>
        <Link to="/uploadortho">
          <button className="primary-button">+ Загрузить ортофотоплан</button>
        </Link>
      </div>

      {loadingOrthos && <div>Загрузка ортофотопланов...</div>}
      {errorOrthos && <div style={{ color: "red" }}>{errorOrthos}</div>}

      {!loadingOrthos && !errorOrthos && orthos.length === 0 && (
        <div className="empty-state">Нет загруженных ортофотопланов</div>
      )}

      {!loadingOrthos && !errorOrthos && orthos.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Превью</th>
              <th>Границы (W,S,E,N)</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {orthos.map((ortho) => (
              <tr key={String(ortho.id)}>
                <td>{ortho.filename}</td>
                <td>
                  <img src={ortho.url} alt="preview" style={{ width: "100px", border: "1px solid #ccc" }} />
                </td>
                <td>
                  {ortho.bounds
                    ? `${ortho.bounds.west}, ${ortho.bounds.south}, ${ortho.bounds.east}, ${ortho.bounds.north}`
                    : "Нет данных"}
                </td>
                <td>
                  <div className="actions-group">
                    <button className="icon-button" onClick={() => window.open(ortho.url, "_blank")} title="Открыть">
                      &darr;
                    </button>
                    <button className="danger-button" onClick={() => handleDeleteOrtho(ortho.id)} title="Удалить">
                      &times;
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  const renderDashboard = () => (
    <div className="development-notice">
      <h2>🚧 Страница в разработке</h2>
      <p>Мы активно работаем над этим разделом</p>
    </div>
  );

  // -------------------------------------------------------------------------
  //                                РЕНДЕР
  // -------------------------------------------------------------------------

  return (
    <div className="background">
      <Header />
      <div className="profile-page">
        <div className="navigation-tabs">
          <button
            className={`tab-button ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            Обзор
          </button>
          <button
            className={`tab-button ${activeTab === "panoramas" ? "active" : ""}`}
            onClick={() => setActiveTab("panoramas")}
          >
            Панорамы
          </button>
          <button
            className={`tab-button ${activeTab === "ortho" ? "active" : ""}`}
            onClick={() => setActiveTab("ortho")}
          >
            Ортофотопланы
          </button>
          <button
            className={`tab-button ${activeTab === "dashboard" ? "active" : ""}`}
            onClick={() => setActiveTab("dashboard")}
          >
            Дашборд
          </button>
        </div>

        <div className="tab-content">
          {activeTab === "overview" && renderOverview()}
          {activeTab === "panoramas" && renderPanoramas()}
          {activeTab === "ortho" && renderOrtho()}
          {activeTab === "dashboard" && renderDashboard()}
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
