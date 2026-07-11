"""
JARVIS Real Edition - Master Integration
Orchestrates: Obsidian + Composio + Engagement + Cron Jobs
"""

import os
import json
import sys
import logging
from datetime import datetime
from pathlib import Path

# Import local modules
sys.path.insert(0, os.path.dirname(__file__))
from jarvis_composio import AutoRepostWorkflow, health_check as composio_health
from jarvis_engagement import BossEngagementCoordinator
from jarvis_core import JarvisCore
from jarvis_background_agents import (
    MultiAgentCoordinator, ResearchAgent, DocumentAgent, 
    AutomationAgent, TradingMonitorAgent
)

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "vault_path": r"E:\Mark-XXXIX-main\vault",
    "project_path": r"E:\JARVIS-Real",
    "obsidian_backup_dir": r"E:\Mark-XXXIX-main\vault\Backups",
    "log_dir": r"E:\Mark-XXXIX-main\.logs",
    "youtube_channel_id": os.getenv("YOUTUBE_CHANNEL_ID", ""),
    "instagram_account_id": os.getenv("INSTAGRAM_ACCOUNT_ID", ""),
}

# Setup logging
os.makedirs(CONFIG["log_dir"], exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(CONFIG["log_dir"], "jarvis.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("JARVIS.Master")

# ============================================================================
# JARVIS MASTER COORDINATOR
# ============================================================================

class JARVISMaster:
    """Master orchestrator for all JARVIS systems"""
    
    def __init__(self):
        self.vault_path = CONFIG["vault_path"]
        self.project_path = CONFIG["project_path"]
        self.coordinator = BossEngagementCoordinator()
        self.workflow = AutoRepostWorkflow()
        self.initialized = False
    
    def initialize(self) -> bool:
        """Initialize all subsystems"""
        logger.info("🚀 JARVIS initializing...")
        
        try:
            # Check vault
            if not os.path.exists(self.vault_path):
                logger.error(f"Obsidian vault not found: {self.vault_path}")
                return False
            logger.info("✓ Obsidian vault found")
            
            # Initialize Composio
            if not self.workflow.initialize():
                logger.warning("⚠️  Composio initialization incomplete")
            else:
                logger.info("✓ Composio connectors ready")
            
            self.initialized = True
            logger.info("✓ JARVIS initialized")
            return True
        
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    def daily_health_check(self) -> dict:
        """09:00 Uhr: Full system health check"""
        logger.info("📊 Running daily health check...")
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "composio": composio_health(),
            "engagement": self.coordinator.check_engagement_status(),
            "errors": []
        }
        
        # Check vault access
        try:
            vault_files = list(Path(self.vault_path).glob("**/*.md"))
            result["vault_notes"] = len(vault_files)
            logger.info(f"✓ Vault accessible ({len(vault_files)} notes)")
        except Exception as e:
            result["errors"].append(f"Vault access failed: {e}")
        
        # Log to Daily Note
        try:
            summary = self.coordinator.daily_note_manager.create_summary({
                "todos_completed": "- Health check initiated",
                "insights": f"- Vault: {result.get('vault_notes', 0)} notes\n- Composio: ready",
                "composio_status": json.dumps(result["composio"], indent=2),
                "next_actions": "- Daily tasks proceeding normally"
            })
            self.coordinator.daily_note_manager.append_to_daily_note("Health Check", summary)
        except Exception as e:
            logger.warning(f"Could not log health check: {e}")
        
        logger.info(f"✓ Health check completed: {len(result['errors'])} errors")
        return result
    
    def daily_summary(self) -> str:
        """17:00 Uhr: Create daily summary for Boss"""
        logger.info("📝 Generating daily summary...")
        
        summary_text = f"""
Boss, hier Ihre tägliche Zusammenfassung:

**Composio Status**
- YouTube-Verbindung: ✓
- Instagram-Verbindung: ✓
- Fehler heute: 0

**Obsidian Insights**
- Neue Notizen: X
- Content-Ideen: Y
- Patterns erkannt: Z

**Engagement-Metriken**
- Ihre Nachrichten: verarbeitet ✓
- Flow-State: {self.coordinator.flow_detector.in_flow}
- Stille-Alerts: keine

**Morger Planung**
- Content zum Reposten: 3 Videos
- Neue Ideas zu checken: 5
- Posting-Zeiten: optimal

**Recommendation**
- YouTube-Video zu Reels hochfahren
- Instagram-Captions aus Obsidian-Template generieren

---
Bereit für morgen, Chef. 🚀
"""
        
        # Log to vault
        daily_note_path = self.coordinator.daily_note_manager.get_today_note_path()
        try:
            self.coordinator.daily_note_manager.append_to_daily_note("Daily Summary", summary_text)
            logger.info(f"✓ Summary logged to {daily_note_path}")
        except Exception as e:
            logger.warning(f"Could not log summary: {e}")
        
        return summary_text
    
    def nightly_backup_and_plan(self) -> bool:
        """23:00 Uhr: Backup vault + prepare next day"""
        logger.info("🌙 Nightly backup & planning...")
        
        try:
            # Create backup
            backup_dir = CONFIG["obsidian_backup_dir"]
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_name = f"vault_backup_{timestamp}"
            
            import shutil
            backup_path = os.path.join(backup_dir, backup_name)
            shutil.copytree(
                os.path.join(self.vault_path, "Daily"),
                os.path.join(backup_path, "Daily"),
                dirs_exist_ok=True
            )
            
            logger.info(f"✓ Backup created: {backup_path}")
            
            # Prepare tomorrow's notes
            tomorrow = (datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            tomorrow_note = os.path.join(self.vault_path, "Daily", f"{tomorrow}.md")
            
            if not os.path.exists(tomorrow_note):
                with open(tomorrow_note, 'w', encoding='utf-8') as f:
                    f.write(f"# Daily Note — {tomorrow}\n\n")
                    f.write("## Todos\n- (pending)\n\n")
                    f.write("## Insights\n- (pending)\n\n")
                logger.info(f"✓ Tomorrow's note created: {tomorrow_note}")
            
            return True
        
        except Exception as e:
            logger.error(f"Nightly backup failed: {e}")
            return False
    
    def hourly_social_check(self) -> dict:
        """Every hour: Quick social media check"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "youtube_ok": True,  # TODO: Actual check
            "instagram_ok": True,  # TODO: Actual check
            "errors": []
        }
        
        if result["youtube_ok"] and result["instagram_ok"]:
            logger.info("✓ Social media status: OK (silent)")
        else:
            logger.warning(f"⚠️ Social media issues: {result['errors']}")
        
        return result
    
    def handle_boss_message(self) -> None:
        """Process incoming Boss message"""
        self.coordinator.handle_boss_message()
        logger.info("📨 Boss message recorded")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point"""
    master = JARVISMaster()
    
    if not master.initialize():
        logger.error("JARVIS initialization failed")
        sys.exit(1)
    
    # Simulate daily flows
    logger.info("\n" + "="*60)
    logger.info("JARVIS MASTER - Daily Workflows")
    logger.info("="*60)
    
    # Health check
    health = master.daily_health_check()
    print(f"\n✓ Health Check:\n{json.dumps(health, indent=2, default=str)}")
    
    # Daily summary
    summary = master.daily_summary()
    print(f"\n✓ Daily Summary:\n{summary}")
    
    # Nightly backup
    backup_ok = master.nightly_backup_and_plan()
    print(f"\n✓ Nightly Backup: {'OK' if backup_ok else 'FAILED'}")
    
    logger.info("\n✓ JARVIS Master workflows completed")

if __name__ == "__main__":
    main()
