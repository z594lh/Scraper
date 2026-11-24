import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Breadcrumb, Dropdown, Layout, Menu, Spin, Tag } from 'antd'
import {
  DashboardOutlined,
  DownOutlined,
  RadarChartOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api } from './api'
import Overview from './pages/Overview'
import ProjectPage from './pages/ProjectPage'
import Settings from './pages/Settings'
import type { Project, Site } from './types'

const { Sider, Content } = Layout

interface AppData {
  projects: Project[]
  sites: Site[]
  refresh: () => Promise<void>
}

const AppDataContext = createContext<AppData>({
  projects: [],
  sites: [],
  refresh: async () => {},
})

// eslint-disable-next-line react-refresh/only-export-components
export const useAppData = () => useContext(AppDataContext)

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [openKeys, setOpenKeys] = useState<string[]>(['projects'])

  const refresh = useCallback(async () => {
    const [projectList, siteList] = await Promise.all([api.projects(), api.sites()])
    setProjects(projectList)
    setSites(siteList)
  }, [])

  useEffect(() => {
    refresh().finally(() => setLoading(false))
  }, [refresh])

  const activeProject = projects.find((item) => location.pathname === `/p/${item.slug}`)

  const selectedKeys = location.pathname.startsWith('/p/')
    ? [`/p/${activeProject?.slug ?? ''}`]
    : [location.pathname === '/settings' ? '/settings' : '/']

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: <Link to="/">概览</Link>,
    },
    {
      key: 'projects',
      icon: <RadarChartOutlined />,
      label: '项目',
      children: projects.length
        ? projects.map((project) => ({
            key: `/p/${project.slug}`,
            label: <Link to={`/p/${project.slug}`}>{project.name}</Link>,
          }))
        : [{ key: 'no-project', label: <span style={{ opacity: 0.5 }}>暂无项目</span>, disabled: true }],
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">通知与系统</Link>,
    },
  ]

  const crumbs: { title: ReactNode }[] = [{ title: <Link to="/">概览</Link> }]
  if (activeProject) {
    crumbs.push({
      title: (
        <Dropdown
          trigger={['hover']}
          menu={{
            items: projects.map((project) => ({ key: String(project.id), label: project.name })),
            onClick: ({ key }) => {
              const target = projects.find((project) => String(project.id) === key)
              if (target) navigate(`/p/${target.slug}`)
            },
          }}
        >
          <a>
            项目 <DownOutlined style={{ fontSize: 10 }} />
          </a>
        </Dropdown>
      ),
    })
    crumbs.push({ title: activeProject.name })
  } else if (location.pathname === '/settings') {
    crumbs.push({ title: '通知与系统' })
  } else {
    crumbs.push({ title: '数据看板' })
  }

  return (
    <AppDataContext.Provider value={{ projects, sites, refresh }}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider width={228} style={{ background: '#0f172a' }}>
          <div className="app-logo">
            <div className="app-logo-mark">R</div>
            <div>
              <div className="app-logo-title">数据中心</div>
              <div className="app-logo-sub">Data Center</div>
            </div>
          </div>
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={selectedKeys}
            openKeys={openKeys}
            onOpenChange={(keys) => setOpenKeys(keys as string[])}
            style={{ background: 'transparent', borderInlineEnd: 0 }}
            items={menuItems}
          />
          <div style={{ position: 'absolute', bottom: 16, left: 20 }}>
            <Tag icon={<RadarChartOutlined />} color="blue" style={{ opacity: 0.8 }}>
              v2.0
            </Tag>
          </div>
        </Sider>
        <Layout>
          <Content style={{ padding: '20px 32px 32px', maxWidth: 1400, width: '100%', margin: '0 auto' }}>
            <Breadcrumb items={crumbs} style={{ marginBottom: 14 }} />
            {loading ? (
              <div style={{ padding: 80, textAlign: 'center' }}>
                <Spin />
              </div>
            ) : (
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/p/:slug" element={<ProjectPage />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            )}
          </Content>
        </Layout>
      </Layout>
    </AppDataContext.Provider>
  )
}
