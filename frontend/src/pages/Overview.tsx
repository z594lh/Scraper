import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
} from 'antd'
import { PlusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAppData } from '../App'
import SiteConfigForm from '../components/SiteConfigForm'
import NotifyRulesForm from '../components/NotifyRulesForm'
import type { ItemRow, NotifyRules, Overview as OverviewData, Project, Site } from '../types'

const DEFAULT_RULES: NotifyRules = {
  newItems: { enabled: true, threshold: 1 },
  runFailed: { enabled: true },
  runFinished: { enabled: false },
}

const statusTag = (project: Project) => {
  if (project.running) return <Tag color="processing">抓取中</Tag>
  const run = project.lastRun
  if (!run) return <Tag>未运行</Tag>
  if (run.status === 'success') return <Tag color="success">成功</Tag>
  if (run.status === 'failed') return <Tag color="error">失败</Tag>
  return <Tag>{run.status}</Tag>
}

export default function Overview() {
  const { projects, sites, refresh } = useAppData()
  const navigate = useNavigate()
  const [messageApi, contextHolder] = message.useMessage()
  const [data, setData] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [name, setName] = useState('')
  const [siteCode, setSiteCode] = useState('panzhi')
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [scheduleMinutes, setScheduleMinutes] = useState(0)
  const [channels, setChannels] = useState<string[]>([])
  const [rules, setRules] = useState<NotifyRules>(DEFAULT_RULES)
  const [siteOptions, setSiteOptions] = useState<Record<string, string[]>>({})

  const load = async () => {
    setLoading(true)
    try {
      setData(await api.overview())
    } catch (error) {
      messageApi.error((error as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 站点枚举（抓取时同步）随站点切换加载
  useEffect(() => {
    if (!siteCode) return
    api
      .siteOptions(siteCode)
      .then((data) =>
        setSiteOptions(
          Object.fromEntries(data.categories.map((item) => [item.category, item.options])),
        ),
      )
      .catch(() => setSiteOptions({}))
  }, [siteCode])

  const activeSite: Site | undefined = sites.find((site) => site.code === siteCode)

  const openCreate = () => {
    const site = sites[0]
    setSiteCode(site?.code ?? '')
    setConfig(site ? { ...site.defaultConfig } : {})
    setName('')
    setScheduleMinutes(0)
    setChannels([])
    setRules(DEFAULT_RULES)
    setCreating(true)
  }

  const submit = async () => {
    if (!name.trim()) {
      messageApi.warning('请填写项目名称')
      return
    }
    setSubmitting(true)
    try {
      const project = await api.createProject({
        name: name.trim(),
        site: siteCode,
        config,
        scheduleMinutes,
        notifyChannels: channels,
        notifyRules: rules,
      })
      messageApi.success('项目已创建')
      setCreating(false)
      await refresh()
      await load()
      navigate(`/p/${project.slug}`)
    } catch (error) {
      messageApi.error((error as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const runNow = async (project: Project) => {
    try {
      await api.runProject(project.id)
      messageApi.success(`${project.name} 已开始抓取`)
      await load()
    } catch (error) {
      messageApi.error((error as Error).message)
    }
  }

  const recentColumns = [
    { title: '项目', dataIndex: 'projectName', width: 160, ellipsis: true },
    {
      title: '编号',
      dataIndex: 'goodsNo',
      width: 110,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      title: '价格',
      dataIndex: 'price',
      width: 100,
      render: (value: number) => (value == null ? '-' : <span className="price">¥{value.toLocaleString()}</span>),
    },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    {
      title: '首次发现',
      dataIndex: 'firstSeenAt',
      width: 150,
      render: (value: string) => <span className="muted">{value ?? '-'}</span>,
    },
  ]

  return (
    <div>
      {contextHolder}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 className="page-title">概览</h2>
          <div className="page-sub">
            所有站点项目的数据汇总；点击项目进入它自己的数据看板。
          </div>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建项目
          </Button>
        </Space>
      </div>

      {loading ? (
        <div style={{ padding: 80, textAlign: 'center' }}>
          <Spin />
        </div>
      ) : (
        <>
          <Row gutter={16} style={{ marginBottom: 20 }}>
            <Col xs={24} md={8}>
              <div className="stat-card">
                <div className="stat-value">{data?.totals.projects ?? 0}</div>
                <div className="stat-label">监控项目</div>
              </div>
            </Col>
            <Col xs={24} md={8}>
              <div className="stat-card">
                <div className="stat-value">{data?.totals.items ?? 0}</div>
                <div className="stat-label">在售账号</div>
              </div>
            </Col>
            <Col xs={24} md={8}>
              <div className="stat-card">
                <div className="stat-value">{data?.totals.newItems ?? 0}</div>
                <div className="stat-label">最近新增</div>
              </div>
            </Col>
          </Row>

          <Row gutter={[16, 16]}>
            {projects.map((project) => (
              <Col xs={24} md={12} xl={8} key={project.id}>
                <div className="project-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div className="project-name">{project.name}</div>
                      <div className="muted" style={{ marginTop: 4 }}>
                        {project.siteLabel} · <code>{project.table}</code>
                      </div>
                    </div>
                    {statusTag(project)}
                  </div>
                  <Row gutter={8} style={{ margin: '16px 0' }}>
                    <Col span={12}>
                      <div className="stat-value" style={{ fontSize: 22 }}>
                        {project.itemCount}
                      </div>
                      <div className="stat-label">在售</div>
                    </Col>
                    <Col span={12}>
                      <div className="stat-value" style={{ fontSize: 22 }}>
                        {project.newCount}
                      </div>
                      <div className="stat-label">NEW</div>
                    </Col>
                  </Row>
                  <Space>
                    <Link to={`/p/${project.slug}`}>
                      <Button type="primary" ghost>
                        进入看板
                      </Button>
                    </Link>
                    <Button
                      icon={<ThunderboltOutlined />}
                      disabled={project.running}
                      onClick={() => runNow(project)}
                    >
                      {project.running ? '抓取中' : '立即抓取'}
                    </Button>
                  </Space>
                </div>
              </Col>
            ))}
            {!projects.length ? (
              <Col span={24}>
                <Empty description="还没有项目，点击右上角新建" />
              </Col>
            ) : null}
          </Row>

          <Card
            size="small"
            title="最近入库"
            style={{ marginTop: 24 }}
            extra={<span className="muted">最多 20 条，跨项目汇总</span>}
          >
            <Table
              size="small"
              rowKey={(row: ItemRow) => `${row.projectId}-${row.goodsNo}`}
              columns={recentColumns}
              dataSource={data?.recentItems ?? []}
              pagination={false}
              scroll={{ x: 'max-content' }}
            />
          </Card>
        </>
      )}

      <Modal
        title="新建项目"
        open={creating}
        width={760}
        onCancel={() => setCreating(false)}
        onOk={submit}
        confirmLoading={submitting}
        okText="创建"
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="项目名称" required>
                <Input
                  value={name}
                  placeholder="例如：盼之 · 浮生若梦"
                  onChange={(event) => setName(event.target.value)}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="站点" required>
                <Select
                  value={siteCode}
                  options={sites.map((site) => ({
                    value: site.code,
                    label: `${site.label}（${site.code}）`,
                  }))}
                  onChange={(next) => {
                    setSiteCode(next)
                    const site = sites.find((item) => item.code === next)
                    setConfig(site ? { ...site.defaultConfig } : {})
                  }}
                />
              </Form.Item>
            </Col>
          </Row>
          <div className="muted" style={{ marginBottom: 12 }}>
            {activeSite?.description} 数据表：<code>{activeSite?.table}</code>
          </div>
          {activeSite ? (
            <SiteConfigForm
              schema={activeSite.configSchema}
              value={config}
              onChange={setConfig}
              options={siteOptions}
            />
          ) : null}
          <Row gutter={16} style={{ marginTop: 8 }}>
            <Col span={12}>
              <Form.Item label="定时抓取间隔（分钟，0=关闭）">
                <InputNumber
                  min={0}
                  max={1440}
                  style={{ width: '100%' }}
                  value={scheduleMinutes}
                  onChange={(next) => setScheduleMinutes(next ?? 0)}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="通知渠道">
                <Checkbox.Group
                  value={channels}
                  onChange={(next) => setChannels(next as string[])}
                  options={[
                    { label: '钉钉', value: 'dingtalk' },
                    { label: '企业微信', value: 'wecom' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <NotifyRulesForm value={rules} onChange={setRules} />
        </Form>
      </Modal>
    </div>
  )
}
