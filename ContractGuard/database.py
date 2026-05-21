def save(self):
    self.db.set("ContractGuard", "contracts", self.contracts)
    self.db.set("ContractGuard", "auto_enabled", self.auto_enabled)
    self.db.set("ContractGuard", "auto_group", self.auto_group)
    self.db.set("ContractGuard", "waiting_users", self.waiting_users)
