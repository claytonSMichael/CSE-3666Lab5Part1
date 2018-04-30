from hardware import Memory, RegisterFile, Register, MUX_2_1, ALU_32, AND_2
import utilities 
from signals import Signals
from time import sleep

class Core_SC: 
	def __init__(self):
		self.I_Mem = Memory()
		self.D_Mem = Memory()
		self.RF = RegisterFile()
		self.RegPC = Register()
		self.signals = Signals()
		self.cycle_num = 0
		self.mode = 0

	def set_PC(self, pc):
		self.RegPC.set_data(pc)
		self.RegPC.set_write(1)

	def set_mode(self, mode):
		self.mode = mode

	def run(self, n_cycles):
		i_cycles = 0
		ending_PC = self.I_Mem.get_ending_address() 

		self.I_Mem.set_memread(1)
		self.I_Mem.set_memwrite(0)

		while (n_cycles == 0 or i_cycles < n_cycles):
			i_cycles += 1
			self.cycle_num += 1
			if ((self.mode & 2) == 0): utilities.print_new_cycle(self.cycle_num)

			# clock changes
			self.RegPC.clock()
			self.RF.clock()

			# read PC
			self.signals.PC = self.RegPC.read()
			self.signals.PC_4 = self.signals.PC_new = self.signals.PC + 4
			if ((self.mode & 2) == 0): utilities.println_int("PC", self.signals.PC)
			if (self.signals.PC > ending_PC): 
				if ((self.mode & 2) == 0): print("No More Instructions")
				i_cycles -= 1 
				break

			self.I_Mem.set_address(self.signals.PC)
			self.I_Mem.run()
			self.signals.instruction = self.I_Mem.get_data() 

			if ((self.mode & 2) == 0): utilities.println_int("instruction", self.signals.instruction)

			# Now you have PC and the instruction
			# Some signals' value can be extracted from instruction directly 
			self.signals_from_instruction(self.signals.instruction, self.signals)

			# call main_control
			self.main_control(self.signals.opcode, self.signals)
			
			# call sign_extend
			self.signals.Sign_extended_immediate = self.sign_extend(self.signals.immediate)
			
			# Write_register. Also an example of using MUX
			self.signals.Write_register = MUX_2_1(self.signals.rt, self.signals.rd, self.signals.RegDst) 
			
			# ALU control
			self.signals.ALU_operation = self.ALU_control(self.signals.ALUOp, self.signals.funct)
			
			# Calculate branch address 
			self.signals.Branch_address = self.calculate_branch_address(self.signals.PC_4, self.signals.Sign_extended_immediate)
			self.signals.Jump_address = self.calculate_jump_address(self.signals.PC_4, self.signals.instruction)
			
			# Print out signals generated in Phase 1.
			if ((self.mode & 4) == 0): utilities.print_signals_1(self.signals)

			# If phase 1 only, continue to the next instruction.
			if ((self.mode & 1) != 0):
				self.RegPC.set_data(self.signals.PC_4)
				self.RegPC.set_write(1)
				continue
			
			###					Register File Inputs				###
			self.RF.set_read_registers(self.signals.rs, self.signals.rt)
			self.signals.Write_register = MUX_2_1(self.signals.rt, self.signals.rd, self.signals.RegDst)
			self.RF.set_write_register(self.signals.Write_register)
			self.RF.set_regwrite(self.signals.RegWrite)
	
			###					Register File Outputs				###
			self.signals.RF_read_data_1 = self.RF.get_read_data_1()
			self.signals.RF_read_data_2 = self.RF.get_read_data_2()
		
			###					ALU	Inputs							###	
			self.signals.ALU_input_2 = MUX_2_1(self.signals.RF_read_data_2, self.signals.Sign_extended_immediate, self.signals.ALUSrc)

			###					ALU Outputs							###
			self.signals.ALU_result = self.signals.ALU_returned_value[0]
			self.signals.ALU_Zero = self.signals.ALU_returned_value[1]
			self.signals.ALU_returned_value = ALU_32(self.signals.RF_read_data_1, self.signals.ALU_input_2, self.signals.ALU_operation)
		
			###					D-Memory Inputs						###
			self.D_Mem.set_memread(self.signals.MemRead)
			self.D_Mem.set_memwrite(self.signals.MemWrite)
			self.D_Mem.set_address(self.signals.ALU_result)
			self.D_Mem.set_data(self.signals.RF_read_data_2)
						
			###					D-Memory Outputs					###
			self.D_Mem.run()
			self.signals.Mem_read_data = self.D_Mem.get_data()

			###					I-Memory Write Data					###
			self.signals.Write_data = MUX_2_1(self.signals.ALU_result, self.signals.Mem_read_data, self.signals.MemtoReg)
			self.RF.set_write_data(self.signals.Write_data)
			
			###					Calculate New PC					###
			self.signals.PCSrc = AND_2(self.signals.Branch, self.signals.ALU_Zero)
			self.signals.PC_branch = MUX_2_1(self.signals.PC_4, self.signals.Branch_address, self.signals.PCSrc)
			self.signals.PC_new = MUX_2_1(self.signals.PC_branch, self.signals.Jump_address, self.signals.Jump)

			self.RegPC.set_data(self.signals.PC_new)
			self.RegPC.set_write(1)

			# Print out signals generated in Phase 2.
			if ((self.mode & 8) == 0): utilities.print_signals_2(self.signals)
		return i_cycles
			
	def signals_from_instruction (self, instruction, sig):
			hex_reg = 0x1F
			hex_4 = 0x457
			hex_5 = 0x3F
			hex_16 = 0xFFFF
			
			sig.opcode = (instruction >> 26) & hex_5
			sig.rs = (instruction >> 21) & hex_reg
			sig.rt = (instruction >> 16) & hex_reg
			sig.rd = (instruction >> 11) & hex_reg
			sig.funct = instruction & hex_5
			sig.immediate = instruction & hex_16

			
	def main_control(self, opcode, sig):
		"""
		Check the type of input instruction
		"""
		#set defaults for control signals 
		sig.RegDst = sig.Jump = sig.Branch = sig.MemRead = sig.MemtoReg = sig.ALUOp = sig.MemWrite = sig.ALUSrc = sig.RegWrite = 0

		#determine control signals
		if opcode == 0:
			sig.RegDst = 1 
			sig.Jump = 0
			sig.Branch = 0
			sig.MemRead = 0
			sig.MemtoReg = 0
			sig.MemWrite = 0
			sig.ALUSrc = 0
			sig.RegWrite = 1
	
			if sig.funct == 32:
				sig.ALUOp = 2
			
			elif sig.funct == 34:
				sig.ALUOp = 6
			
			elif sig.funct == 36:
				sig.ALUOp = 0
			
			elif sig.funct == 37:
				sig.ALUOp = 1
	
			else:
				sig.ALUOp = 7
	
		elif opcode == 8:
			sig.RegDst = 0 
			sig.Jump = 0
			sig.Branch = 0
			sig.MemRead = 0
			sig.MemtoReg = 0
			sig.MemWrite = 0
			sig.ALUSrc = 1
			sig.RegWrite = 1
			sig.ALUOp = 0

		#lw
		elif opcode == 35:
			sig.RegDst = 0 
			sig.Jump = 0
			sig.Branch = 0
			sig.MemRead = 1
			sig.MemtoReg = 1
			sig.MemWrite = 0
			sig.ALUSrc = 1
			sig.RegWrite = 1
			sig.ALUOp = 0
		#sw	
		elif opcode == 43:
			sig.RegDst = 0 
			sig.Jump = 0
			sig.Branch = 0
			sig.MemRead = 0
			sig.MemtoReg = 0
			sig.MemWrite = 1
			sig.ALUSrc = 1
			sig.RegWrite = 0
			sig.ALUop = 0
		#beq	
		elif opcode == 4:
			sig.RegDst = 0 
			sig.Jump = 0
			sig.Branch = 1
			sig.MemRead = 0
			sig.MemtoReg = 0
			sig.MemWrite = 0
			sig.ALUSrc = 0
			sig.RegWrite = 0
			sig.ALUOp = 1

		else:
			sig.RegDst = 0 
			sig.Jump = 1
			sig.Branch = 0
			sig.MemRead = 0
			sig.MemtoReg = 0
			sig.MemWrite = 0
			sig.ALUSrc = 0
			sig.RegWrite = 0
			sig.ALUOp = 0

	def ALU_control(self, alu_op, funct):  
		"""
		Get alu_control from func field of instruction
		Input: function field of instruction
		Output: alu_control_out
	   
		"""
		alu_control_out = 0
		# One example is given, continue to finish other cases.
		if alu_op == 0:				# 00  
			alu_control_out = 2		# 0010
		elif alu_op == 1:
			alu_control_out = 6
		elif alu_op == 2:
			if funct == 32:
				alu_control_out = 2
			elif funct == 34:
				alu_control_out = 6
			elif funct == 36:
				alu_control_out = 0
			elif funct == 37:
				alu_control_out = 1
			else:
				alu_control_out = 7			

		return alu_control_out

	def sign_extend(self, immd):
		"""
		Sign extend module. 
		Convert 16-bit to an int.
		Extract the lower 16 bits. 
		If bit 15 of immd is 1, compute the correct negative value (immd - 0x10000).
		"""
	
		baseHex = (0x0000FFFF & immd)
		zeroHex = 0x00000000
	
		sign = (immd & 0xFFFF) >> 15

		if (sign == 1):
			baseHex += 0xFFFF0000

		return baseHex	
	
	def calculate_branch_address(self, pc_4, extended):
		addr = 0
		addr += (extended << 2) + pc_4
		return addr

	def calculate_jump_address(self, pc_4, instruction):
		addr = ((instruction & 0x3FFFFFF) << 2) | (pc_4 & 0xF0000000)
		return addr

