import { createRouter, createWebHistory } from 'vue-router'
import { setupGuards } from './guards'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // ==================== Auth ====================
    {
      path: '/login',
      component: () => import('@/pages/auth/Login.vue'),
      meta: { public: true },
    },
    {
      path: '/register',
      component: () => import('@/pages/auth/Register.vue'),
      meta: { public: true },
    },

    // ==================== Student ====================
    {
      path: '/student',
      component: () => import('@/layouts/LayoutStudent.vue'),
      meta: { role: 'student' },
      children: [
        { path: 'dashboard', component: () => import('@/pages/student/Dashboard.vue') },
        { path: 'knowledge', component: () => import('@/pages/student/KnowledgeExplore.vue') },
        { path: 'practice', component: () => import('@/pages/student/PracticeHome.vue') },
        { path: 'practice/panel', component: () => import('@/pages/student/Practice.vue') },
        { path: 'exercise-records', component: () => import('@/pages/student/ExerciseRecords.vue') },
        { path: 'subject-records', component: () => import('@/pages/student/SubjectRecords.vue') },
        { path: 'chat', component: () => import('@/pages/student/Chat.vue') },
        { path: 'plan', component: () => import('@/pages/student/LearningPlan.vue') },
        { path: 'ocr', component: () => import('@/pages/student/OcrParse.vue') },
        { path: 'kg-pipeline', component: () => import('@/pages/student/KgPipeline.vue') },
        { path: 'interactive', component: () => import('@/pages/student/InteractiveZone.vue') },
        { path: 'interactive/:id', component: () => import('@/pages/student/InteractiveDetail.vue') },
        { path: 'messages', component: () => import('@/pages/student/MessageNotifications.vue') },
      ],
    },

    // ==================== Teacher ====================
    {
      path: '/teacher',
      component: () => import('@/layouts/LayoutTeacher.vue'),
      meta: { role: 'teacher' },
      children: [
        { path: 'dashboard', component: () => import('@/pages/teacher/Analytics.vue') },
        { path: 'chat', component: () => import('@/pages/teacher/Chat.vue') },
        { path: 'interactive', component: () => import('@/pages/teacher/InteractiveZone.vue') },
        { path: 'subject', component: () => import('@/pages/teacher/SubjectManage.vue') },
        { path: 'kg-manage', component: () => import('@/pages/teacher/KnowledgeGraphManage.vue') },
      ],
    },

    // ==================== Admin ====================
    {
      path: '/admin',
      component: () => import('@/layouts/LayoutAdmin.vue'),
      meta: { role: 'admin' },
      children: [
        { path: 'ocr', component: () => import('@/pages/student/OcrParse.vue') },
        { path: 'kg-pipeline', component: () => import('@/pages/student/KgPipeline.vue') },
        { path: 'students', component: () => import('@/pages/teacher/StudentManage.vue') },
        { path: 'alerts', component: () => import('@/pages/teacher/Alert.vue') },
        { path: ':pathMatch(.*)*', redirect: '/admin/ocr' },
      ],
    },
    {
      path: '/',
      redirect: '/login',
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('@/pages/misc/404.vue'),
      meta: { public: true },
    },
  ],
})

setupGuards(router)

export default router
