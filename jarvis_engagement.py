"""
JARVIS Boss Engagement Monitor
Time-aware greetings + Inactivity detection
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger("JARVIS.Engagement")

# ============================================================================
# TIME-AWARE GREETINGS
# ============================================================================

class TimeAwareGreeting:
    """Generate contextual greetings based on time of day"""
    
    @staticmethod
    def get_greeting() -> str:
        """Get appropriate greeting for current time"""
        hour = datetime.now().hour
        
        # Morgens (6-9 Uhr)
        if 6 <= hour < 9:
            greetings = [
                "Guten Morgen, Boss. Ausgeruht?",
                "Morgen! Kaffee schon dabei?",
                "Guten Tag, Chef. Bereit für heute?"
            ]
        
        # Tagsüber (9-20 Uhr)
        elif 9 <= hour < 20:
            greetings = [
                "Boss, noch am Arbeiten?",
                "Wie läuft's, Chef?",
                "Alles im grünen Bereich?"
            ]
        
        # Abends (20-23:59 Uhr)
        elif 20 <= hour < 24:
            greetings = [
                "Boss, machen Sie die Nacht zum Tag oder gönnen Sie sich Schlaf?",
                "Spät noch wach, Chef? Nicht vergessen: Schlaf ist auch Produktivität.",
                "Abendschicht, Boss?"
            ]
        
        # Nachts (0-6 Uhr)
        else:  # 0 <= hour < 6
            greetings = [
                "Boss, nicht schon wieder eine Durchmach-Nacht, oder?",
                "3 Uhr morgens... verstanden, Flow-State aktiviert? 😏",
                "Nachts am arbeiten? Respekt, Chef."
            ]
        
        import random
        return random.choice(greetings)

# ============================================================================
# INACTIVITY MONITOR
# ============================================================================

class InactivityMonitor:
    """Track silence between Boss messages and alert accordingly"""
    
    SILENCE_THRESHOLDS = {
        "short": (15 * 60, "Boss, noch da?"),  # 15 minutes
        "medium": (1 * 60 * 60, "Boss, leben Sie noch?"),  # 1 hour
        "long": (4 * 60 * 60, "Boss, längeres Schweigen macht mir Sorgen – alles in Ordnung?")  # 4 hours
    }
    
    def __init__(self, state_file: str = None):
        self.state_file = state_file or r"E:\Mark-XXXIX-main\.boss_engagement_state"
        self.last_activity = self._load_state()
    
    def record_activity(self):
        """Record Boss message received"""
        self.last_activity = datetime.now()
        self._save_state(self.last_activity)
        logger.info(f"📍 Boss activity recorded at {self.last_activity}")
    
    def get_silence_alert(self) -> Optional[str]:
        """Check if silence threshold exceeded and return appropriate alert"""
        if not self.last_activity:
            return None
        
        silence_duration = datetime.now() - self.last_activity
        
        # Check thresholds in order
        for level, (threshold_seconds, message) in self.SILENCE_THRESHOLDS.items():
            if silence_duration.total_seconds() > threshold_seconds:
                return message
        
        return None
    
    def _save_state(self, timestamp: datetime):
        """Save last activity to file"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump({
                    "last_activity": timestamp.isoformat()
                }, f)
        except Exception as e:
            logger.warning(f"Could not save engagement state: {e}")
    
    def _load_state(self) -> Optional[datetime]:
        """Load last activity from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data.get("last_activity"))
        except Exception as e:
            logger.warning(f"Could not load engagement state: {e}")
        
        return None

# ============================================================================
# FLOW STATE DETECTION
# ============================================================================

class FlowStateDetector:
    """Detect when Boss is in productive flow and avoid interruptions"""
    
    def __init__(self):
        self.in_flow = False
        self.flow_start_time = None
        self.message_frequency_threshold = 2  # messages per minute = flow
    
    def update_activity_rate(self, recent_messages: int, time_window_minutes: int):
        """
        Analyze message frequency to detect flow state
        High frequency = Boss is in flow, don't interrupt
        """
        message_rate = recent_messages / time_window_minutes if time_window_minutes > 0 else 0
        
        if message_rate >= self.message_frequency_threshold:
            if not self.in_flow:
                self.in_flow = True
                self.flow_start_time = datetime.now()
                logger.info("🎯 Flow state detected - minimize interruptions")
        else:
            if self.in_flow:
                duration = datetime.now() - self.flow_start_time
                logger.info(f"✓ Flow state ended (duration: {duration})")
            self.in_flow = False

# ============================================================================
# DAILY NOTE MANAGER
# ============================================================================

class DailyNoteManager:
    """Manage Obsidian Daily Notes"""
    
    def __init__(self, vault_path: str = r"E:\Mark-XXXIX-main\vault"):
        self.vault_path = vault_path
        self.daily_dir = os.path.join(vault_path, "Daily")
    
    def get_today_note_path(self) -> str:
        """Get path to today's daily note"""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.daily_dir, f"{today}.md")
    
    def append_to_daily_note(self, section: str, content: str):
        """Append content to today's daily note"""
        try:
            note_path = self.get_today_note_path()
            os.makedirs(os.path.dirname(note_path), exist_ok=True)
            
            # Check if section exists
            if os.path.exists(note_path):
                with open(note_path, 'r', encoding='utf-8') as f:
                    existing = f.read()
                
                # Find or create section
                if f"## {section}" not in existing:
                    existing += f"\n## {section}\n{content}\n"
                else:
                    # Append to existing section
                    existing = existing.replace(
                        f"## {section}",
                        f"## {section}\n{content}"
                    )
                
                with open(note_path, 'w', encoding='utf-8') as f:
                    f.write(existing)
            else:
                # Create new daily note
                with open(note_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Daily Note — {datetime.now().strftime('%d.%m.%Y')}\n\n")
                    f.write(f"## {section}\n{content}\n")
            
            logger.info(f"✓ Appended to daily note: {section}")
        
        except Exception as e:
            logger.error(f"Failed to append to daily note: {e}")
    
    def create_summary(self, summary_data: dict) -> str:
        """Create formatted summary for daily note"""
        summary = f"""
## Daily Summary ({datetime.now().strftime('%H:%M')})

### Todos Completed
{summary_data.get('todos_completed', '- (none)')}

### Insights
{summary_data.get('insights', '- (none)')}

### Composio Status
{summary_data.get('composio_status', '- OK')}

### Next Actions
{summary_data.get('next_actions', '- (pending)')}
"""
        return summary

# ============================================================================
# MAIN ENGAGEMENT COORDINATOR
# ============================================================================

class BossEngagementCoordinator:
    """Central coordinator for all Boss engagement features"""
    
    def __init__(self):
        self.inactivity_monitor = InactivityMonitor()
        self.flow_detector = FlowStateDetector()
        self.daily_note_manager = DailyNoteManager()
    
    def handle_boss_message(self):
        """Process incoming Boss message"""
        self.inactivity_monitor.record_activity()
        logger.info("📨 Boss message processed")
    
    def get_contextual_greeting(self) -> str:
        """Generate greeting with time awareness"""
        return TimeAwareGreeting.get_greeting()
    
    def check_engagement_status(self) -> dict:
        """Get current engagement status and alerts"""
        status = {
            "silence_alert": self.inactivity_monitor.get_silence_alert(),
            "in_flow": self.flow_detector.in_flow,
            "greeting": self.get_contextual_greeting()
        }
        return status

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    coordinator = BossEngagementCoordinator()
    
    # Simulate Boss activity
    coordinator.handle_boss_message()
    
    # Check status
    status = coordinator.check_engagement_status()
    print(f"Engagement Status: {json.dumps(status, indent=2, default=str)}")
    
    # Create daily summary
    summary_data = {
        "todos_completed": "- [ ] Composio init\n- [ ] Obsidian setup",
        "insights": "- Boss Mode Protocol active\n- Cron jobs scheduled",
        "composio_status": "- YouTube: connected\n- Instagram: waiting for API key",
        "next_actions": "- Integrate Composio SDK\n- Test auto-repost workflow"
    }
    summary = coordinator.daily_note_manager.create_summary(summary_data)
    coordinator.daily_note_manager.append_to_daily_note("Status Update", summary)
    
    print("\n✓ JARVIS Engagement module ready")
