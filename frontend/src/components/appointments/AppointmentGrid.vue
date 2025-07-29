<template>
  <div class="appointment-grid-container min-h-screen bg-gray-100">
    <!-- Header with Date Controls -->
    <div class="sticky top-0 z-20 bg-white border-b border-gray-300 shadow-sm">
      <div class="px-6 py-4">
        <div class="flex items-center justify-between flex-wrap gap-4">
          <div class="flex items-center space-x-6">
            <h1 class="text-2xl font-semibold text-black">Appointments</h1>
            
            <!-- Company Selector -->
            <div class="flex items-center">
              <Link
                class="form-control min-w-[240px]"
                :value="selectedCompany || ''"
                doctype="Company"
                placeholder="Select Company"
                @change="handleCompanyChange"
                variant="outline"
              />
            </div>
            
            <!-- Date Controls -->
            <div class="flex items-center space-x-2">
              <Button variant="ghost" @click="goToPreviousDay">
                <FeatherIcon name="chevron-left" class="h-4 w-4 text-black" />
              </Button>
              
              <DatePicker
                v-model="selectedDateForPicker"
                variant="outline"
                placeholder="Select Date"
                @change="handleDateChange"
                class="min-w-[200px]"
              />
              
              <Button variant="ghost" @click="goToNextDay">
                <FeatherIcon name="chevron-right" class="h-4 w-4 text-black" />
              </Button>
            </div>
          </div>
          
          <div class="flex items-center space-x-3">
            <div class="relative">
              <FeatherIcon name="search" class="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-600" />
              <TextInput
                placeholder="Search practitioners..."
                class="pl-10 w-64 text-black"
                v-model="searchQuery"
              />
            </div>
            <Button @click="refreshData" :loading="isRefreshing">
              <FeatherIcon name="refresh-cw" class="h-4 w-4 mr-2 text-black" />
              <span class="text-black">Refresh</span>
            </Button>
          </div>
        </div>
        
        <div class="py-2">
          <div class="text-sm text-gray-500">
            {{ formattedDate }}
          </div>
        </div>
      </div>
    </div>

    <!-- Main Grid Container -->
    <div class="appointment-grid">
      <!-- Time Column -->
      <div class="time-column">
        <!-- Time Slots Header -->
        <div class="time-header">
          <div class="h-24 border-b-2 border-gray-200 bg-gray-50 flex items-center justify-center sticky top-0 z-40">
            <span class="text-sm font-semibold text-gray-600">Time Slots</span>
          </div>
        </div>

        <!-- Time Slots Body - Scrollable -->
        <div class="time-slots" ref="timeSlots">
          <div
            v-for="slot in dateStore.timeSlots"
            :key="slot.time"
            class="time-slot"
            :class="{ 
              'current-time': isCurrentTimeSlot(slot)
            }"
          >
            <div class="flex flex-col items-center">
              <span class="text-sm font-bold text-gray-900">{{ slot.display }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Practitioners Area -->
      <div class="practitioners-area" ref="practitionersArea">
        <!-- Practitioners Header with Navigation Controls -->
        <div class="practitioners-header-container">
          <!-- Practitioners Header - Fixed -->
          <div class="practitioners-header-fixed" ref="practitionersHeader">
            <div class="flex gap-4">
              <div v-if="practitionerStore.filteredPractitioners.length === 0" class="flex items-center justify-center min-w-[320px] h-full border-b-2 border-gray-300">
                <span class="text-gray-500 text-sm">No practitioners found</span>
              </div>
              <div 
                v-for="practitioner in practitionerStore.filteredPractitioners"
                :key="practitioner.name"
                class="practitioner-header-cell"
              >
                <PractitionerCard :practitioner="practitioner" />
              </div>
            </div>
          </div>
        </div>

        <!-- Scrollable Appointments Grid -->
        <div class="appointments-grid" ref="appointmentsGrid">
          <div class="grid-content">
            <div
              v-for="slot in dateStore.timeSlots"
              :key="slot.time"
              class="grid-row"
              :class="{ 
                'current-time': isCurrentTimeSlot(slot)
              }"
            >
              <div
                v-for="practitioner in practitionerStore.filteredPractitioners"
                :key="`${slot.time}-${practitioner.name}`"
                class="grid-cell"
                :class="{ 
                  'bg-gray-50': !practitioner.is_available
                }"
              >
                <!-- Existing Appointment -->
                <AppointmentCard
                  v-if="getAppointment(slot.time, practitioner.name)"
                  :appointment="getAppointment(slot.time, practitioner.name)"
                  @click="viewAppointment"
                  @complete="handleCompleteAppointment"
                  @cancel="handleCancelAppointment"
                />
                
                <!-- Break Time Slot -->
                <div
                  v-else-if="slot.isDuringBreak"
                  class="break-slot"
                  :title="slot.breakLabel"
                >
                  <span class="text-xs font-bold text-orange-800">{{ slot.breakLabel || 'Break' }}</span>
                </div>
                
                <!-- Empty Slot with Add Button -->
                <div
                  v-else-if="canAddAppointment(slot, practitioner)"
                  class="add-appointment-button group"
                  @click="createAppointment(slot.time, practitioner)"
                  :title="`Create appointment for ${practitioner.name} at ${slot.display}`"
                >
                  <div class="add-button-content">
                    <FeatherIcon name="plus" class="h-4 w-4 text-gray-900 group-hover:text-blue-600 transition-colors" />
                    <span class="add-text text-xs font-bold text-gray-900 group-hover:text-blue-600 transition-colors mt-1">Add</span>
                  </div>
                </div>
                
                <!-- Unavailable Slot -->
                <div
                  v-else
                  class="unavailable-slot"
                  :title="getUnavailableReason(slot, practitioner)"
                >
                  <span class="text-xs font-bold text-gray-600">—</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Scroll Controls -->
    <div class="bottom-scroll-controls">
      <!-- Left Scroll Button -->
      <button
        v-if="canScrollLeft"
        @click="scrollHorizontally('left')"
        class="scroll-control scroll-control-left"
        :disabled="!canScrollLeft"
        title="Scroll left"
      >
        <FeatherIcon name="chevron-left" class="h-5 w-5 text-white drop-shadow-sm" />
      </button>

      <!-- Right Scroll Button -->
      <button
        v-if="canScrollRight"
        @click="scrollHorizontally('right')"
        class="scroll-control scroll-control-right"
        :disabled="!canScrollRight"
        title="Scroll right"
      >
        <FeatherIcon name="chevron-right" class="h-5 w-5 text-white drop-shadow-sm" />
      </button>
    </div>

    <!-- Appointment Dialog -->
    <AppointmentDialog />
    
    <!-- Confirmation Dialog -->
    <Dialog v-model="showConfirmDialog" :options="confirmDialogOptions">
      <template #body-content>
        <p class="text-gray-600">{{ confirmMessage }}</p>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { onMounted, computed, ref, onUnmounted, nextTick, watch } from 'vue'
// All Frappe UI components are now globally available from main.js
import { useAppointmentStore } from '@/stores/appointment'
import { usePractitionerStore } from '@/stores/practitioner'
import { useDateStore } from '@/stores/date'
import PractitionerCard from './PractitionerCard.vue'
import AppointmentCard from './AppointmentCard.vue'
import AppointmentDialog from './AppointmentDialog.vue'
import Link from '../controls/Link.vue'
import { notifications } from '@/utils/notifications'
import dayjs from 'dayjs'

const appointmentStore = useAppointmentStore()
const practitionerStore = usePractitionerStore()
const dateStore = useDateStore()

// Refs for DOM elements
const gridContainer = ref(null)
const practitionersArea = ref(null)
const practitionersHeader = ref(null)
const appointmentsGrid = ref(null)
const timeSlots = ref(null)

// State
const isRefreshing = ref(false)
const showConfirmDialog = ref(false)
const confirmMessage = ref('')
const confirmAction = ref(null)
const searchQuery = ref('')
const selectedCompany = ref('')
const selectedDateForPicker = ref('')
const userCompanies = ref([])

// Horizontal scroll control state
const canScrollLeft = ref(false)
const canScrollRight = ref(false)
const scrollAmount = 320 // 2 practitioner cards width (160px each)

// Initialize selectedDateForPicker with current date
onMounted(() => {
  selectedDateForPicker.value = dateStore.selectedDate
  // Ensure selectedCompany has a default value
  if (!selectedCompany.value) {
    selectedCompany.value = ''
  }
})

// Company options for Select component  
const companyOptions = computed(() => {
  return userCompanies.value.map(company => ({
    label: company.name,
    value: company.name
  }))
})

// Computed properties
const appointments = computed(() => appointmentStore.todaysAppointments)

const formattedDate = computed(() => {
  return dayjs(dateStore.selectedDate).format('dddd, MMMM D, YYYY')
})

const confirmDialogOptions = computed(() => ({
  title: 'Confirm Action',
  actions: [
    {
      label: 'Cancel',
      variant: 'outline'
    },
    {
      label: 'Confirm',
      variant: 'solid',
      theme: 'red',
      handler: () => {
        if (confirmAction.value) {
          confirmAction.value()
        }
        showConfirmDialog.value = false
      }
    }
  ]
}))

// Initialize data
onMounted(async () => {
  try {
    console.log('🔄 Initializing appointment grid...')

    // Fetch user companies first
    await fetchUserCompanies()

    // Sync dates between stores initially
    appointmentStore.setSelectedDate(dateStore.selectedDate)
    selectedDateForPicker.value = dateStore.selectedDate

    // Set initial company in appointment store if one is selected
    if (selectedCompany.value) {
      appointmentStore.setSelectedCompany(selectedCompany.value)
    }

    await Promise.all([
      dateStore.generateTimeSlots(),
      selectedCompany.value ? practitionerStore.fetchPractitioners(selectedCompany.value, dateStore.selectedDate) : Promise.resolve()
    ])
    
    setupSynchronizedScrolling()

    // Add window resize listener for scroll button states
    window.addEventListener('resize', updateScrollButtonStates)

  } catch (error) {
    console.error('❌ Error initializing appointment grid:', error)
    notifications.error.dataLoadFailed(error.message)
  }
})

onUnmounted(() => {
  cleanupSynchronizedScrolling()
  window.removeEventListener('resize', updateScrollButtonStates)
})

// Watch for date changes
watch(
  () => dateStore.selectedDate,
  async (newDate) => {
    console.log('🔍 DateStore date changed to:', newDate)
    selectedDateForPicker.value = newDate
    appointmentStore.setSelectedDate(newDate) // Update appointment store date
    if (selectedCompany.value && selectedCompany.value.trim()) {
      practitionerStore.fetchPractitioners(selectedCompany.value, dateStore.selectedDate)
    }
  }
)

// Watch for company changes
watch(
  selectedCompany,
  async (newCompany) => {
    if (newCompany && newCompany.trim()) {
      appointmentStore.setSelectedCompany(newCompany)
      await Promise.all([
        practitionerStore.fetchPractitioners(newCompany, dateStore.selectedDate),
        appointmentStore.fetchAppointments()
      ])
    }
  }
)

// Watch for search query changes
watch(
  searchQuery,
  (newQuery) => {
    practitionerStore.setSearchQuery(newQuery)
  }
)

// Watch for practitioners changes to update scroll states
watch(
  () => practitionerStore.filteredPractitioners,
  () => {
    nextTick(() => {
      updateScrollButtonStates()
    })
  }
)

// Synchronized scrolling setup (vertical only)
let scrollListeners = []

// Simplified vertical-only synchronized scrolling
const setupSynchronizedScrolling = () => {
  nextTick(() => {
    if (appointmentsGrid.value && timeSlots.value) {
      let isScrolling = false

      // Vertical sync: appointments grid to time slots
      const handleAppointmentsGridScroll = () => {
        if (isScrolling) return
        isScrolling = true
        
        const scrollTop = appointmentsGrid.value.scrollTop
        
        // Sync vertical with time slots only
        if (timeSlots.value.scrollTop !== scrollTop) {
          timeSlots.value.scrollTop = scrollTop
        }
        
        // Update horizontal scroll button states
        updateScrollButtonStates()
        
        isScrolling = false
      }

      // Vertical sync: time slots to appointments grid
      const handleTimeSlotsScroll = () => {
        if (isScrolling) return
        isScrolling = true
        
        const scrollTop = timeSlots.value.scrollTop
        if (appointmentsGrid.value.scrollTop !== scrollTop) {
          appointmentsGrid.value.scrollTop = scrollTop
        }
        
        isScrolling = false
      }

      // Add event listeners with passive: true for better performance
      appointmentsGrid.value.addEventListener('scroll', handleAppointmentsGridScroll, { passive: true })
      timeSlots.value.addEventListener('scroll', handleTimeSlotsScroll, { passive: true })

      scrollListeners.push(
        () => appointmentsGrid.value?.removeEventListener('scroll', handleAppointmentsGridScroll),
        () => timeSlots.value?.removeEventListener('scroll', handleTimeSlotsScroll)
      )

      // Initial scroll button state check
      updateScrollButtonStates()
    }
  })
}

// Horizontal scroll control functions
const scrollHorizontally = (direction) => {
  if (!practitionersHeader.value || !appointmentsGrid.value) return

  const currentScrollLeft = practitionersHeader.value.scrollLeft
  const newScrollLeft = direction === 'left' 
    ? Math.max(0, currentScrollLeft - scrollAmount)
    : currentScrollLeft + scrollAmount

  // Smooth scroll both elements simultaneously
  practitionersHeader.value.scrollTo({
    left: newScrollLeft,
    behavior: 'smooth'
  })
  
  appointmentsGrid.value.scrollTo({
    left: newScrollLeft,
    top: appointmentsGrid.value.scrollTop,
    behavior: 'smooth'
  })

  // Update button states after scroll animation
  setTimeout(updateScrollButtonStates, 300)
}

const updateScrollButtonStates = () => {
  if (!practitionersHeader.value) return

  const scrollLeft = practitionersHeader.value.scrollLeft
  const maxScrollLeft = practitionersHeader.value.scrollWidth - practitionersHeader.value.clientWidth

  canScrollLeft.value = scrollLeft > 0
  canScrollRight.value = scrollLeft < maxScrollLeft - 1 // -1 for precision issues
}

const cleanupSynchronizedScrolling = () => {
  scrollListeners.forEach(cleanup => cleanup())
  scrollListeners = []
}

// Helper functions
const getAppointment = (timeSlot, practitionerId) => {
  const key = `${timeSlot}-${practitionerId}`
  const appointment = appointmentStore.appointmentsByTimeSlot[key]
  
  return appointment
}

const canAddAppointment = (slot, practitioner) => {
  return (
    practitioner.is_available &&
    !slot.isPast &&
    dateStore.canBookAppointment(slot.time) &&
    !getAppointment(slot.time, practitioner.name)
  )
}

const isCurrentTimeSlot = (slot) => {
  if (!dateStore.isToday) return false
  
  const now = dayjs()
  const slotTime = dayjs(`${dateStore.selectedDate} ${slot.time}`)
  const nextSlotTime = slotTime.add(dateStore.slotDuration, 'minute')
  
  return now.isAfter(slotTime) && now.isBefore(nextSlotTime)
}

const getUnavailableReason = (slot, practitioner) => {
  if (slot.isPast) return 'Past time slot'
  if (slot.isDuringBreak) return `${slot.breakLabel || 'Break time'}`
  if (!practitioner.is_available) return 'Practitioner unavailable'
  if (!dateStore.canBookAppointment(slot.time)) return 'Booking not allowed'
  return 'Unavailable'
}

// Date navigation functions
const goToPreviousDay = () => {
  dateStore.goToPreviousDay()
}

const goToNextDay = () => {
  dateStore.goToNextDay()
}

// Handle date change from DatePicker
const handleDateChange = async(selectedDate) => {
  if (selectedDate) {
    console.log('🔍 Date picker changed to:', selectedDate)
    dateStore.setSelectedDate(selectedDate)

    await Promise.all([
      practitionerStore.fetchPractitioners(selectedCompany.value, selectedDate),
      appointmentStore.fetchAppointments()
    ])

    selectedDateForPicker.value = selectedDate
  }
}

// Handle company change from Link component
const handleCompanyChange = async (selectedCompanyValue) => {
  if (selectedCompanyValue && typeof selectedCompanyValue === 'string') {
    selectedCompany.value = selectedCompanyValue

    await Promise.all([
      practitionerStore.fetchPractitioners(selectedCompanyValue, dateStore.selectedDate),
      appointmentStore.setSelectedCompany(selectedCompanyValue)
    ])

    console.log('Company changed to:', selectedCompanyValue)
  } else if (selectedCompanyValue && selectedCompanyValue.name) {
    // Handle if Link component returns an object
    selectedCompany.value = selectedCompanyValue.name

    await Promise.all([
      practitionerStore.fetchPractitioners(selectedCompanyValue.name, dateStore.selectedDate),
      appointmentStore.setSelectedCompany(selectedCompanyValue.name)
    ])

    console.log('Company changed to:', selectedCompanyValue.name)
  }
}

// Fetch user companies function
const fetchUserCompanies = async () => {
  try {
    // Mock data for now - replace with actual API call
    userCompanies.value = [
      // { name: 'Nephro One Dialysis Clinic' },
      { name: 'Shree Hindu Mandal Hospital - Mwanza' },
    ]
    
    // Set default company if none selected
    if (userCompanies.value.length > 0 && !selectedCompany.value) {
      selectedCompany.value = userCompanies.value[0].name
    }
  } catch (error) {
    console.error('Error fetching user companies:', error)
    userCompanies.value = [{ name: 'Default Company' }]
    selectedCompany.value = 'Default Company'
  }
}

// Event handlers
const createAppointment = (timeSlot, practitioner) => {
  appointmentStore.openAppointmentDialog('create', {
    time_slot: timeSlot,
    practitioner_id: practitioner.name,
    practitioner_name: practitioner.name
  })
}

const viewAppointment = (appointment) => {
  appointmentStore.openAppointmentDialog('view', appointment)
}

const handleCompleteAppointment = (appointment) => {
  confirmMessage.value = `Mark appointment with ${appointment.patient_name} as completed?`
  confirmAction.value = () => completeAppointment(appointment)
  showConfirmDialog.value = true
}

const handleCancelAppointment = (appointment) => {
  confirmMessage.value = `Cancel appointment with ${appointment.patient_name}?`
  confirmAction.value = () => cancelAppointment(appointment)
  showConfirmDialog.value = true
}

const completeAppointment = async (appointment) => {
  try {
    const result = await appointmentStore.completeAppointment(appointment.name)
    if (result.success) {
      notifications.success.appointmentCompleted()
    } else {
      notifications.error.appointmentUpdateFailed(result.error || 'Unknown error')
    }
  } catch (error) {
    notifications.error.appointmentUpdateFailed('Error completing appointment')
    console.error(error)
  }
}

const cancelAppointment = async (appointment) => {
  try {
    const result = await appointmentStore.cancelAppointment(appointment.name)
    if (result.success) {
      notifications.success.appointmentCancelled()
    } else {
      notifications.error.appointmentUpdateFailed(result.error || 'Unknown error')
    }
  } catch (error) {
    notifications.error.appointmentUpdateFailed('Error cancelling appointment')
    console.error(error)
  }
}

const refreshData = async () => {
  if (isRefreshing.value) return
  
  isRefreshing.value = true
  try {
    await Promise.all([
      dateStore.generateTimeSlots(),
      (selectedCompany.value && selectedCompany.value.trim()) ? practitionerStore.fetchPractitioners(selectedCompany.value, dateStore.selectedDate) : Promise.resolve(),
      (selectedCompany.value && selectedCompany.value.trim()) ? appointmentStore.fetchAppointments() : Promise.resolve(),
    ])
    notifications.success.dataRefreshed()
  } catch (error) {
    notifications.error.dataLoadFailed(error.message)
    console.error(error)
  } finally {
    isRefreshing.value = false
  }
}
</script>


<style scoped>
.appointment-grid {
  display: flex;
  height: 100%;
  border-top: 1px solid #d1d5db;
  background-color: white;
  position: relative;
  min-height: calc(80vh - 80px);
  height: calc(100vh - 100px);
}

.time-column {
  width: 7rem;
  flex-shrink: 0;
  background-color: #f9fafb;
  border-right: 1px solid #d1d5db;
  position: relative;
  display: flex;
  flex-direction: column;
}

.time-header {
  position: sticky;
  top: 0;
  z-index: 40;
  background-color: #f9fafb;
  flex-shrink: 0;
}

.practitioners-header-fixed {
  background-color: white;
  border-bottom: 1px solid #d1d5db;
  height: 6rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 50;
  flex-shrink: 0;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: auto; /* Remove smooth scrolling for instant sync */
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* Internet Explorer 10+ */
}

.practitioners-header-fixed::-webkit-scrollbar {
  display: none; /* WebKit */
}

.time-slots {
  /* space-y-0 equivalent: margin-top: 0; margin-bottom: 0; */
  background-color: #f9fafb;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: auto; /* Remove smooth scrolling for instant sync */
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* Internet Explorer 10+ */
}

.time-slots::-webkit-scrollbar {
  display: none; /* WebKit */
}

.time-slot {
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #e5e7eb;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
  text-align: center;
  transition-property: color, background-color, border-color, text-decoration-color, fill, stroke;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
  background-color: #f9fafb;
  height: 108px; /* Match grid cell height + margin */
  min-height: 96px;
}

.time-slot.current-time {
  background-color: #dbeafe;
  color: #1e40af;
  font-weight: 600;
  border-bottom-color: #93c5fd;
}

.grid-row.current-time {
  background-color: #eff6ff;
}

.practitioners-area {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.practitioners-header-container {
  position: relative;
  display: flex;
  align-items: center;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-bottom: 2px solid #e5e7eb;
  height: 96px;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.scroll-control {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(96, 165, 250, 0.25), 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(8px);
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.9) 0%, rgba(59, 130, 246, 0.9) 100%);
  border: 2px solid #60a5fa;
}

.scroll-control:hover:not(:disabled) {
  box-shadow: 0 8px 25px rgba(96, 165, 250, 0.35), 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: scale(1.1);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.95) 0%, rgba(37, 99, 235, 0.95) 100%);
  border-color: #3b82f6;
}

.scroll-control:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background: #9ca3af;
  border-color: #6b7280;
}



.scroll-control:active:not(:disabled) {
  transform: scale(0.95);
  box-shadow: 0 2px 8px rgba(96, 165, 250, 0.3);
}

.scroll-control:focus {
  outline: none;
  box-shadow: 0 4px 12px rgba(96, 165, 250, 0.25), 0 2px 4px rgba(0, 0, 0, 0.1), 0 0 0 2px #3b82f6, 0 0 0 4px rgba(96, 165, 250, 0.2);
}

/* Subtle pulse animation to draw attention */
@keyframes pulse-blue {
  0%, 100% {
    box-shadow: 0 4px 12px rgba(96, 165, 250, 0.25), 0 2px 4px rgba(0, 0, 0, 0.1);
  }
  50% {
    box-shadow: 0 4px 12px rgba(96, 165, 250, 0.4), 0 2px 4px rgba(0, 0, 0, 0.1);
  }
}

.scroll-control:not(:disabled) {
  animation: pulse-blue 3s ease-in-out infinite;
}

/* Entrance animation */
@keyframes slideIn {
  0% {
    opacity: 0;
    transform: scale(0.5);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.scroll-control {
  animation: slideIn 0.3s ease-out;
}

.practitioners-header-fixed {
  background-color: white;
  height: 6rem; /* h-24 equivalent */
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* Internet Explorer 10+ */
  border-radius: 8px;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
}

.practitioners-header-fixed::-webkit-scrollbar {
  display: none; /* WebKit */
}

.appointments-grid-wrapper {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.practitioner-header-cell {
  width: 10rem;
  flex-shrink: 0;
  height: 100%;
  background-color: white;
  border-radius: 0.375rem;
  border-right: 1px dotted #d1d5db;
  border-bottom: 2px dotted #d1d5db;
}

.appointments-grid {
  overflow-y: auto;
  overflow-x: auto;
  scroll-behavior: smooth;
  background: 
    linear-gradient(to right, #f3f4f6 1px, transparent 1px),
    linear-gradient(to bottom, #d1d5db 1px, transparent 1px);
  background-size: 176px 96px; /* 160px width + 16px gap, 96px height to match time slots */
  height: 100%;
  width: 100%;
  border-top: 2px solid #e5e7eb;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.06);
}

.appointments-grid::-webkit-scrollbar-horizontal {
  display: none; /* Hide horizontal scrollbar */
}

.appointments-grid::-webkit-scrollbar:vertical {
  width: 0.5rem;
}

.appointments-grid::-webkit-scrollbar-track {
  background-color: #f3f4f6;
}

.appointments-grid::-webkit-scrollbar-thumb {
  background-color: #9ca3af;
  border-radius: 9999px;
}

.appointments-grid::-webkit-scrollbar-thumb:hover {
  background-color: #6b7280;
}

.grid-row {
  display: flex;
  transition-property: color, background-color, border-color, text-decoration-color, fill, stroke;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
  background-color: white;
  gap: 1rem;
  min-height: 96px; /* Match time slot height */
  margin-bottom: 0; /* Remove row margin since cells have their own spacing */
}

.grid-cell {
  width: 10rem;
  flex-shrink: 0;
  position: relative;
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  padding: 0.25rem;
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
  background-color: white;
  height: 100px;
  min-height: 100px;
  margin-bottom: 8px; /* Add space between cards to show bottom borders */
  border-right: 1px dotted #d1d5db;
  border-bottom: 1px dotted #d1d5db;
}

.grid-cell:hover {
  background-color: #eff6ff;
}

.add-appointment-button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
  border: 1px dotted #9ca3af;
  border-radius: 0.375rem;
  height: 86px; /* Slightly smaller than cell to show spacing */
  background-color: #f8f9fa;
}

.add-appointment-button:hover {
  background-color: #bfdbfe;
  border-color: #2563eb;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

.add-appointment-button:hover .add-button-content {
  transform: scale(1.1);
}

.add-appointment-button:active {
  transform: scale(0.95);
}

.add-button-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.add-button-content .add-text {
  font-size: 0.75rem;
  line-height: 1rem;
  font-weight: 700;
}

.unavailable-slot {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4b5563;
  background-color: #e5e7eb;
  border: 1px dotted #9ca3af;
  border-radius: 0.375rem;
}

.break-slot {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #fed7aa;
  color: #9a3412;
  border: 1px dotted #f97316;
  border-radius: 0.375rem;
}

/* Enhanced visual elements for better grid visibility */
.current-time-indicator {
  position: absolute;
  left: 0;
  right: 0;
  height: 0.125rem;
  background-color: #ef4444;
  z-index: 20;
  box-shadow: 0 0 4px rgba(239, 68, 68, 0.5);
}

/* Focus styles for accessibility */
.add-appointment-button:focus {
  outline: 2px solid transparent;
  outline-offset: 2px;
  box-shadow: 0 0 0 2px #3b82f6, 0 0 0 4px rgba(59, 130, 246, 0.2);
}

.practitioners-header-fixed:focus,
.appointments-grid:focus {
  outline: 2px solid transparent;
  outline-offset: 2px;
  box-shadow: 0 0 0 2px #3b82f6, 0 0 0 4px rgba(59, 130, 246, 0.2);
}

/* Current time slot highlighting */
.time-slot.current-time {
  background-color: #fecaca;
  border-bottom-color: #fca5a5;
  color: #b91c1c;
  font-weight: 700;
  box-shadow: inset 3px 0 0 #ef4444;
}

.grid-row.current-time {
  background-color: #fef2f2;
  border-color: #fca5a5;
}

.grid-row.current-time .grid-cell {
  border-color: #fecaca;
}

/* Synchronized scrolling */
.practitioners-header-fixed,
.appointments-grid {
  scroll-behavior: smooth;
}

/* Bottom scroll controls */
.bottom-scroll-controls {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  z-index: 1000;
  pointer-events: none; /* Allow clicks to pass through the container */
}

.bottom-scroll-controls .scroll-control {
  pointer-events: auto; /* Re-enable clicks on the buttons */
}

/* Mobile responsive adjustments */
@media (max-width: 768px) {
  .appointment-grid-container {
    font-size: 0.875rem;
    line-height: 1.25rem;
  }
  
  .time-column {
    width: 5rem;
  }
  
  .grid-cell, .practitioner-header-cell {
    width: 9rem;
    height: 80px;
    min-height: 80px;
  }
  
  .time-slot {
    height: 80px;
    min-height: 80px;
  }
  
  .practitioners-header {
    height: 80px;
  }
}

@media (max-width: 640px) {
  .grid-cell, .practitioner-header-cell {
    width: 8rem;
    height: 4rem;
    min-height: 64px;
  }
  
  .time-slot {
    height: 4rem;
    font-size: 0.75rem;
    line-height: 1rem;
    min-height: 64px;
  }
  
  .time-column {
    width: 5rem;
  }
  
  .practitioners-header {
    height: 4rem;
  }
  
  .appointment-grid-container .px-6 {
    padding-left: 1rem;
    padding-right: 1rem;
  }
  
  .appointment-grid-container .py-4 {
    padding-top: 0.75rem;
    padding-bottom: 0.75rem;
  }
}

/* Loading and error states */
.loading-overlay {
  position: absolute;
  inset: 0;
  background-color: rgba(255, 255, 255, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}

/* Smooth transitions */
.appointment-card {
  transition-property: all;
  transition-duration: 200ms;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}

.appointment-card:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

/* High contrast mode support */
@media (prefers-contrast: high) {
  .grid-cell {
    border-color: #9ca3af;
  }
  
  .time-slot {
    border-color: #9ca3af;
  }
  
  .appointment-card {
    border: 2px solid;
  }
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .appointment-card,
  .add-appointment-button,
  .time-slot,
  .grid-row,
  .grid-cell {
    transition: none;
  }
  
  .practitioners-header,
  .appointments-grid {
    scroll-behavior: auto;
  }
}
</style>
