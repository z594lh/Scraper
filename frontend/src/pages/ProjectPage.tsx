import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  message,
  Row,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
} from 'antd'
import { LoginOutlined, ReloadOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useParams } from 'react-router-dom'
import { api } from '../api'
import { useAppData } from '../App'
import ItemsTable from '../components/ItemsTable'
import NotifyRulesForm from '../components/NotifyRulesForm'
import SiteConfigForm from '../components/SiteConfigForm'
import type { ItemsPayload, NotifyRules, Project, Run } from '../types'

const runStatus = (status: string) => {
  if (status === 'success') return <Tag color="success">成功</Tag>
  if (status === 'failed') return <Tag color="error">失败</Tag>
  return <Tag color="processing">运行中</Tag>
}

export default function ProjectPage() {
  const { slug = '' } = useParams()
  const { projects, refresh } = useAppData()
  const basic = projects.find((item) => item.slug === slug)
  const [messageApi, contextHolder] = message.useMessage()
  const [project, setProject] = useState<Project | null>(null)
  const [payload, setPayload] = useState<ItemsPayload | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [tab, setTab] = useState('data')
  const [search, setSearch] = useState('')
  const [onlyNew, setOnlyNew] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState<Record<string, unknown>>({})
  const [projectName, setProjectName] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [scheduleMinutes, setScheduleMinutes] = useState(0)
  const [channels, setChannels] = useState<string[]>([])
  const [rules, setRules] = useState<NotifyRules>({
    newItems: { enabled: true, threshold: 1 },
    runFailed: { enabled: true },
    runFinished: { enabled: false },
  })
  const [siteOptions, setSiteOptions] = useState<Record<string, string[]>>({})

  const load = async (projectId: number, options?: { onlyNew?: boolean; q?: string }) => {
    const [detail, items, runList] = await Promise.all([
      api.project(projectId),
      api.items(projectId, { onlyNew: options?.onlyNew ?? onlyNew, q: options?.q ?? search }),
      api.runs(projectId),
    ])
    setProject(detail)
    setPayload(items)
    setRuns(runList)
    setConfig(detail.config)
    setProjectName(detail.name)
    setEnabled(detail.enabled)
    setScheduleMinutes(detail.scheduleMinutes)
    setChannels(detail.notifyChannels)
    setRules(detail.notifyRules)
    const optionsData = await api.siteOptions(detail.site)
    setSiteOptions(
      Object.fromEntries(optionsData.categories.map((item) => [item.category, item.options])),
    )
  }

  useEffect(() => {
    if (!basic) {
      setLoading(false)
      return
    }
    setLoading(true)
    load(basic.id)
      .catch((error) => messageApi.error((error as Error).message))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basic?.id])

  const busy = Boolean(project?.running || project?.login?.state === 'running')

  useEffect(() => {
    if (!project || !busy) return
    const timer = setInterval(() => {
      load(project.id).catch(() => undefined)
    }, 3000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, busy])

  if (!basic) {
    return <Empty description="项目不存在或已删除" />
  }

  if (loading || !project) {
    return (
      <div style={{ padding: 80, textAlign: 'center' }}>
        <Spin />
      </div>
    )
  }

  const runNow = async () => {
    try {
      await api.runProject(project.id)
      messageApi.success('已开始抓取，页面会自动刷新')
      await load(project.id)
    } catch (error) {
      messageApi.error((error as Error).message)
    }
  }

  const doLogin = async () => {
    try {
      const state = await api.login(project.id)
      setProject({ ...project, login: state })
      messageApi.info(state.message || '已打开登录窗口')
    } catch (error) {
      messageApi.error((error as Error).message)
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      const updated = await api.updateProject(project.id, {
        name: projectName,
        enabled,
        config,
        scheduleMinutes,
        notifyChannels: channels,
        notifyRules: rules,
      })
      setProject(updated)
      await refresh()
      messageApi.success('已保存')
    } catch (error) {
      messageApi.error((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const columns = payload?.columns ?? project.siteSpec?.columns ?? []

  const dataTab = (
    <div>
      <Space style={{ marginBottom: 14 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索编号 / 标题"
          style={{ width: 240 }}
          onSearch={(value) => {
            setSearch(value)
            load(project.id, { q: value }).catch((error) => messageApi.error((error as Error).message))
          }}
        />
        <Checkbox
          checked={onlyNew}
          onChange={(event) => {
            setOnlyNew(event.target.checked)
            load(project.id, { onlyNew: event.target.checked }).catch(() =>
              messageApi.error('加载失败'),
            )
          }}
        >
          只看 NEW
        </Checkbox>
        <span className="muted">
          数据表 <code>{payload?.table ?? project.table}</code>，共 {payload?.items.length ?? 0} 条
        </span>
      </Space>
      <ItemsTable columns={columns} items={payload?.items ?? []} loading={loading} />
    </div>
  )

  const runsTab = (
    <Table
      size="small"
      rowKey="id"
      dataSource={runs}
      pagination={{ pageSize: 10, hideOnSinglePage: true }}
      expandable={{
        expandedRowRender: (run: Run) => (
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>{run.log || '（无日志）'}</pre>
        ),
        rowExpandable: (run: Run) => Boolean(run.log),
      }}
      columns={[
        { title: '开始时间', dataIndex: 'startedAt', width: 170 },
        { title: '触发', dataIndex: 'trigger', width: 90 },
        { title: '状态', dataIndex: 'status', width: 90, render: (value: string) => runStatus(value) },
        {
          title: '耗时',
          dataIndex: 'duration',
          width: 90,
          render: (value: number | null) => (value == null ? '-' : `${value}s`),
        },
        { title: '抓取', dataIndex: 'total', width: 80 },
        { title: '新增', dataIndex: 'newCount', width: 80 },
        {
          title: '说明',
          dataIndex: 'message',
          ellipsis: true,
          render: (value: string) =>
            value ? (
              <Tooltip title={value}>
                <span className="item-title">{value}</span>
              </Tooltip>
            ) : (
              <span className="muted">-</span>
            ),
        },
      ]}
    />
  )

  const configTab = (
    <Card size="small" style={{ maxWidth: 900 }}>
      <Form layout="vertical">
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="项目名称">
              <Input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="启用定时抓取">
              <Switch checked={enabled} onChange={setEnabled} />
            </Form.Item>
          </Col>
        </Row>
        <SiteConfigForm
          schema={project.siteSpec?.configSchema ?? []}
          value={config}
          onChange={setConfig}
          options={siteOptions}
        />
        <Row gutter={16} style={{ marginTop: 12 }}>
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
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
          保存配置
        </Button>
      </Form>
    </Card>
  )

  return (
    <div>
      {contextHolder}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 className="page-title">{project.name}</h2>
          <Space size={6} wrap className="page-sub">
            <Tag color="blue">{project.siteLabel}</Tag>
            <code>{project.table}</code>
            <span className="muted">slug: {project.slug}</span>
            {project.running ? <Tag color="processing">抓取中</Tag> : null}
            {!project.enabled ? <Tag>已停用</Tag> : null}
          </Space>
        </div>
        <Space>
          <Button icon={<LoginOutlined />} onClick={doLogin} disabled={project.login.state === 'running'}>
            登录
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => load(project.id)}>
            刷新
          </Button>
          <Button type="primary" icon={<ThunderboltOutlined />} disabled={project.running} onClick={runNow}>
            立即抓取
          </Button>
        </Space>
      </div>

      {project.login.state === 'running' ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="登录窗口已打开"
          description={project.login.message || '请在弹出的浏览器窗口完成登录，完成后会自动关闭'}
        />
      ) : null}
      {project.login.state === 'failed' ? (
        <Alert type="error" showIcon style={{ marginBottom: 12 }} message="登录失败" description={project.login.message} />
      ) : null}
      {project.lastRun?.status === 'failed' ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="最近一次抓取失败"
          description={project.lastRun.message}
        />
      ) : null}

      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: 'data', label: `数据看板 (${project.itemCount})`, children: dataTab },
          { key: 'runs', label: '运行记录', children: runsTab },
          { key: 'config', label: '项目配置', children: configTab },
        ]}
      />
    </div>
  )
}
